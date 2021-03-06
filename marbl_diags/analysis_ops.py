"""
Functions that can be called from analysis elements"""

import os
from subprocess import call
import numpy as np
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
import cartopy
import cartopy.crs as ccrs
import esmlab
from . import plottools as pt

def plot_ann_climo(AnalysisElement, config_dict):
    """ Regardless of data source, generate plots based on annual climatology"""
    # set up time dimension for averaging
    valid_time_dims = dict()
    for ds_name, data_source in AnalysisElement.data_sources.items():
        # 1. data source needs time dimension of 1 or 12
        if data_source.ds.dims['time'] not in [1, 12]:
            raise ValueError("Dataset '{}' must have time dimension of 1 or 12".format(ds_name))
        # 2. set up averages to reflect proper dimensions
        valid_time_dims[ds_name] = dict()
        valid_time_dims[ds_name]['ANN'] = range(0,data_source.ds.dims['time'])
    _plot_climo(AnalysisElement, config_dict, valid_time_dims)

def plot_mon_climo(AnalysisElement, config_dict):
    """ Regardless of data source, generate plots based on monthly climatology"""
    # set up time dimension for averaging
    valid_time_dims = dict()
    for ds_name, data_source in AnalysisElement.data_sources.items():
        # 1. data source needs time dimension of 12
        if data_source.ds.dims['time'] != 12:
            raise ValueError("Dataset '{}' must have time dimension of 12".format(ds_name))
        # 2. set up averages to reflect proper dimensions
        valid_time_dims[ds_name] = dict()
        valid_time_dims[ds_name]['ANN'] = range(0,12)
        valid_time_dims[ds_name]['DJF'] = [11, 0, 1]
        valid_time_dims[ds_name]['MAM'] = range(2,5)
        valid_time_dims[ds_name]['JJA'] = range(5,8)
        valid_time_dims[ds_name]['SON'] = range(8,11)
    _plot_climo(AnalysisElement, config_dict, valid_time_dims)

def _plot_climo(AnalysisElement, config_dict, valid_time_dims):
    """ Regardless of data source, generate plots """
    # look up grid (move to known grids database)
    if AnalysisElement._config_dict['grid'] == 'POP_gx1v7':
        # and is tracer....
        depth_coord_name = 'z_t'
    else:
        raise ValueError('unknown grid')

    # where will plots be written?
    if not os.path.exists(AnalysisElement._config_dict['dirout']):
        call(['mkdir', '-p', AnalysisElement._config_dict['dirout']])

    # identify reference (if any provided)
    ref_data_source_name = None
    if AnalysisElement.reference:
        for data_source_name in AnalysisElement.data_sources:
            if AnalysisElement.reference == data_source_name:
                ref_data_source_name = data_source_name
    if ref_data_source_name:
        AnalysisElement.logger.info("Reference dataset: '%s'", ref_data_source_name)
    else:
        AnalysisElement.logger.info("No reference dataset specified")

    #-- loop over datasets
    data_source_name_list = AnalysisElement.data_sources.keys()
    if ref_data_source_name:
        data_source_name_list = [ref_data_source_name] + \
                                [data_source_name for data_source_name in data_source_name_list
                                    if data_source_name != ref_data_source_name]

    #-- loop over variables
    for v in AnalysisElement._config_dict['variable_list']:

        nrow, ncol = pt.get_plot_dims(len(data_source_name_list))
        AnalysisElement.logger.info('dimensioning plot canvas: %d x %d (%d total plots)',
                         nrow, ncol, len(data_source_name_list))

        #-- loop over time periods
        for time_period in config_dict['climo_time_periods']:

            for sel_z in AnalysisElement._config_dict['depth_list']:

                #-- build indexer for depth
                if isinstance(sel_z, list): # fragile?
                    is_depth_range = True
                    indexer = {depth_coord_name:slice(sel_z[0], sel_z[1])}
                    depth_str = '{:.0f}-{:.0f}m'.format(sel_z[0], sel_z[1])
                else:
                    is_depth_range = False
                    indexer = {depth_coord_name: sel_z, 'method': 'nearest'}
                    depth_str = '{:.0f}m'.format(sel_z)

                #-- name of the plot
                plot_name = 'state-map-{}_{}_{}_{}'.format(AnalysisElement._config_dict['short_name'],
                                                           v,
                                                           depth_str,
                                                           time_period)
                AnalysisElement.logger.info('generating plot: %s', plot_name)

                #-- generate figure object
                AnalysisElement.fig[plot_name] = plt.figure(figsize=(ncol*6,nrow*4))
                AnalysisElement.axs[plot_name] = np.empty(ncol*nrow, dtype=type(None))
                AnalysisElement.fig[plot_name].suptitle("{} at {}".format(v, depth_str))

                for i, ds_name in enumerate(data_source_name_list):

                    ds = AnalysisElement.data_sources[ds_name].ds
                    #-- need to deal with time dimension here....

                    # Find appropriate variable name in dataset
                    var_name = AnalysisElement.data_sources[ds_name]._var_dict[v]
                    if var_name not in ds:
                        raise KeyError('Can not find {} in {}'.format(var_name, ds_name))
                    if time_period in valid_time_dims[ds_name]:
                        field = ds[var_name].sel(**indexer).isel(time=valid_time_dims[ds_name][time_period]).mean('time')
                    else:
                        raise KeyError("'{}' is not a known time period for '{}'".format(time_period, ds_name))
                    AnalysisElement.logger.info('Plotting %s from %s', var_name, ds_name)

                    if is_depth_range:
                        field = field.mean(depth_coord_name)

                    # Get stats (probably refactor this at some point)
                    if AnalysisElement._config_dict['stats_in_title']:
                        # TAREA is needed for weighted means
                        if 'time' in ds['TAREA'].dims:
                            TAREA = ds['TAREA'].isel(time=0)
                        else:
                            TAREA = ds['TAREA']
                        fmin = np.nanmin(field)
                        fmax = np.nanmax(field)
                        fmean = esmlab.statistics.weighted_mean(field, TAREA).load().values
                        fRMS = np.sqrt(esmlab.statistics.weighted_mean(field*field, TAREA).load().values)


                    AnalysisElement.axs[plot_name][i] = AnalysisElement.fig[plot_name].add_subplot(nrow, ncol, i+1, projection=ccrs.Robinson(central_longitude=305.0))

                    if AnalysisElement._config_dict['grid'] == 'POP_gx1v7':
                        lon, lat, field = pt.adjust_pop_grid(ds.TLONG.values, ds.TLAT.values, field)

                    if v not in AnalysisElement._var_dict:
                        raise KeyError('{} not defined in variable YAML dict'.format(v))

                    AnalysisElement.axs[plot_name][i].background_patch.set_facecolor('gray')
                    cf = AnalysisElement.axs[plot_name][i].contourf(lon,lat,field,transform=ccrs.PlateCarree(),
                                                                    levels=AnalysisElement._var_dict[v]['contours']['levels'],
                                                                    extend=AnalysisElement._var_dict[v]['contours']['extend'],
                                                                    cmap=AnalysisElement._var_dict[v]['contours']['cmap'],
                                                                    norm=pt.MidPointNorm(midpoint=AnalysisElement._var_dict[v]['contours']['midpoint']))
                    del(field)

                    # land = AnalysisElement.axs[plot_name][i].add_feature(cartopy.feature.NaturalEarthFeature(
                    #     'physical','land','110m',
                    #     edgecolor='face',
                    #     facecolor='gray'))

                    if AnalysisElement._config_dict['stats_in_title']:
                        title_str = "{}\nMin: {:.2f}, Max: {:.2f}, Mean: {:.2f}, RMS: {:.2f}".format(
                             ds_name, fmin, fmax, fmean, fRMS)
                        AnalysisElement.logger.info(title_str)
                        AnalysisElement.axs[plot_name][i].set_title(title_str)
                    else:
                        AnalysisElement.axs[plot_name][i].set_title(ds_name)
                    AnalysisElement.axs[plot_name][i].set_xlabel('')
                    AnalysisElement.axs[plot_name][i].set_ylabel('')

                AnalysisElement.fig[plot_name].subplots_adjust(hspace=0.45, wspace=0.02, right=0.9)
                cax = plt.axes((0.93, 0.15, 0.02, 0.7))
                AnalysisElement.fig[plot_name].colorbar(cf, cax=cax)

                if AnalysisElement._config_dict['plot_format']:
                    AnalysisElement.fig[plot_name].savefig('{}/{}.{}'.format(AnalysisElement._config_dict['dirout'],
                                                  plot_name,
                                                  AnalysisElement._config_dict['plot_format']),
                                bbox_inches='tight', dpi=300, format=AnalysisElement._config_dict['plot_format'])
                plt.close(AnalysisElement.fig[plot_name])
                if not AnalysisElement._config_dict['keep_figs']:
                    del(AnalysisElement.fig[plot_name])
                    (AnalysisElement.axs[plot_name])
    if not AnalysisElement._config_dict['keep_figs']:
        del(AnalysisElement.fig)
        (AnalysisElement.axs)