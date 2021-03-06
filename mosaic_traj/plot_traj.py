#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Plot output from ROTRAJ trajectory model

This module was developed by CEMAC as part of the ACRoBEAR
Project.

.. module:: plot_traj
   :synopsis: Plot trajectory data

.. moduleauthor:: Tamora D. James <t.d.james1@leeds.ac.uk>, CEMAC (UoL)

:copyright: © 2022 University of Leeds.
:license: BSD 3-clause (see LICENSE)


Example::

plot_traj.py <path> --track <track_file> --out <out_dir> --start <start_date> --end <end_date>

<path> Path to trajectory data

<track_file> Path to CSV containing ship track data

<out_dir> Output directory

<start_date> Start date in ISO format YYYY-MM-DD

<end_date> End date (inclusive) in ISO format YYYY-MM-DD

"""
# standard library imports
import os
import sys
import datetime as dt
import argparse
import math

# third party imports
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # use Agg backend for matplotlib
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# local imports
from read_traj import read_traj, read_data


def parse_args():
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=formatter)

    parser.add_argument('path', type=str,
                        metavar='trajectory data',
                        help='''Path to trajectory data''')

    parser.add_argument('--track', type=str,
                        metavar='track file',
                        help='''Path to ship track data''')

    parser.add_argument('--out', type=str,
                        metavar='output directory',
                        help='''Path to output directory''')

    parser.add_argument('--start', type=str,
                        metavar='start date',
                        help='''Start date''')

    parser.add_argument('--end', type=str,
                        metavar='end date',
                        help='''End date''')

    parser.add_argument('--freq', type=int,
                        metavar='frequency', default=15,
                        help='''Frequency at which to plot trajectories''')

    pa = parser.parse_args()

    # Check if path exists
    if pa.path and not os.path.exists(pa.path):
        err_msg = "Path {0} does not exist\n".format(pa.path)
        raise ValueError(err_msg)

    # Check if track file exists
    if pa.track and not os.path.exists(pa.track):
        err_msg = "File {0} does not exist\n".format(pa.track)
        raise ValueError(err_msg)

    # Check if output directory exists
    if pa.out and not os.path.isdir(pa.out):
        err_msg = "Path {0} is not a directory \n".format(pa.out)
        raise ValueError(err_msg)

    return (pa.path, pa.track, pa.out, pa.start, pa.end, pa.freq)


def main():

    rtraj_path, track_file, out_dir, start, end, freq = parse_args()

    plot_data = []
    if start is not None:
        plot_data = read_data(rtraj_path, start, end)
    else:
        plot_data.append(read_traj(rtraj_path))

    fig, ax = plt.subplots(figsize=(9,9),
                           subplot_kw=dict(projection=ccrs.Orthographic(0, 90)))
    ax.coastlines(zorder=3)
    ax.add_feature(cfeature.LAND)
    ax.add_feature(cfeature.OCEAN)
    ax.gridlines()

    nday = len(plot_data)
    depth = 4
    alpha = [math.exp(-x*depth/nday) for x in reversed(range(nday))]
    dates = []
    traj_dt = None
    for i, (data, metadata) in enumerate(plot_data):
        timestamp = metadata['trajectory base time']
        traj_dt = dt.datetime.strptime(timestamp, '%Y%m%d00')
        if i == 0:
            dates.append(traj_dt.strftime('%Y%m%d'))

        periods = math.floor(len(data.groupby(level=0))/freq)
        dt_index = pd.date_range(traj_dt.strftime('%Y%m%d'),
                                 periods=periods, freq=str(freq)+"min")

        for ts in dt_index:
            try:
                traj = data.loc[ts]
            except KeyError:
                # timestamp not available
                continue

            # Get subset of data where P is non-negative and P > 980 and plot
            # trajectory between these points
            ind0 = traj[traj['P (MB)'] > 0].index[0]
            ind1 = traj[(traj['P (MB)'] > 0) & (traj['P (MB)'] < 980)]
            if len(ind1) > 0:
                ind1 = ind1.index[0]
                traj = traj.loc[ind0:ind1]
            else:
                traj = traj.loc[ind0:]

            plt.plot(traj.LON, traj.LAT,
                     color='purple', alpha=alpha[i],
                     transform=ccrs.PlateCarree(),
                     )

    if i > 0:
        dates.append(traj_dt.strftime('%Y%m%d'))

    if track_file is not None:
        track_data = pd.read_csv(track_file, index_col='timestamp')
        track_data.columns = [x.lower() for x in track_data.columns]
        track_sub = track_data[::60]
        plt.plot(track_sub.longitude, track_sub.latitude,
                 color='black', alpha=1.0, linewidth=0, marker='o', markersize=1,
                 transform=ccrs.PlateCarree(),
                 )

    # Set map extent
    ax.set_extent([-180, 180, 60, 90], ccrs.PlateCarree())

    title = ' to '.join(dates)
    plt.title(title)

    file_name = '-'.join(dates) + '.png'
    if out_dir is not None:
        file_name = os.path.join(out_dir, file_name)

    plt.savefig(file_name)
    plt.close()


if __name__ == '__main__':
    main()
