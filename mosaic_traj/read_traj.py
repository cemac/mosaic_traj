#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Read ROTRAJ trajectory data

This module was developed by CEMAC as part of the ACRoBEAR
Project.

.. module:: read_traj
   :synopsis: Read trajectory data

.. moduleauthor:: Tamora D. James <t.d.james1@leeds.ac.uk>, CEMAC (UoL)

:copyright: © 2022 University of Leeds.
:license: BSD 3-clause (see LICENSE)

Example::
        ./read_traj.py <file>

        <file> Path to file containing trajectory data
"""
# standard library imports
import os
import datetime as dt
import argparse
import re
import glob

# third party imports
import pandas as pd


ATTR = {
    1:   'temperature (K)',
    3:   'potential vorticity (PVU)',
    4:   'specific humidity (kg/kg)',
    10:  'height (m)',
    159: 'boundary layer height (m)'
}


def parse_args():
    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=formatter)

    parser.add_argument('file', type=str,
                        metavar='file',
                        help='''Path to trajectory data''')

    pa = parser.parse_args()

    # Check if file exists
    if pa.file and not os.path.exists(pa.file):
        err_msg = "File {0} does not exist\n"
        err_msg = err_msg.format(pa.file)
        raise ValueError(err_msg)

    return (pa.file)


def process_metadata(file):
    '''
    Process trajectory metadata of the form

     TRAJECTORY BASE TIME IS 2019092200
     DATA BASE TIME IS 2021051700
     DATA INTERVAL IS    3 HOURS AND CONTAINS    6 TIMESTEPS
     TOTAL NUMBER OF TRAJECTORIES IS     1440
     NUMBER OF ATTRIBUTES IS    5
     ATTRIBUTE TYPES = 
       1   3   4  10 159
     NUMBER OF CLUSTERS IS    1
     CLUSTER POINTERS = 
          1
     3D TRAJECTORY ? (T OR F): T
     FORECAST DATA ? (T OR F): F
     FORWARD TRAJECTORY ? (T OR F): F

     TRAJECTORY NUMBER     1 COMPRISES    88 INTERVALS

'''
    def get_date(line):
        m = re.search('\d{10}', line)
        if m is not None:
            return m[0]


    def get_numeric(line, type='int'):
        m = re.findall('\d+', line)
        if m is not None:
            if type == 'int':
                m = [int(x) for x in m]
            elif type == 'float':
                m = [float(x) for x in m]
            if len(m) > 1:
                return m
            else:
                return m[0]


    def get_boolean(line):
        m = re.split(':\s*', line)
        if m is not None:
            m = True if m[-1] == 't' else False
        return m


    metadata = {}
    count = 0
    with open(file) as f:
        for i, line in enumerate(f):
            line = line.lower().rstrip('\n')
            if 'trajectory number' in line:
                count = count + i
                break
            elif 'trajectory base time' in line:
                metadata['trajectory base time'] = get_date(line)
            elif 'data base time' in line:
                metadata['data base time'] = get_date(line)
            elif 'data interval' in line:
                # extract data interval and number of timesteps per interval
                vals = get_numeric(line)
                if len(vals) == 2:
                    metadata['data interval hours'] = vals[0]
                    metadata['data interval timesteps'] = vals[1]
                else:
                    raise ValueError(
                        "Unexpected number of values in data interval"
                    )
            elif 'total number of trajectories' in line:
                # extract number of trajectories
                metadata['total number of trajectories'] = get_numeric(line)
            elif 'number of attributes' in line:
                # extract number of attributes
                metadata['number of attributes'] = get_numeric(line)
            elif 'attribute types' in line:
                # get next line, extract attributes
                metadata['attribute types'] = get_numeric(next(f))
                count = count + 1
            elif 'number of clusters' in line:
                # extract number of clusters
                metadata['number of clusters'] = get_numeric(line)
            elif 'cluster pointers' in line:
                # get next line, extract cluster pointers
                metadata['cluster pointers'] = get_numeric(next(f))
                count = count + 1
            elif '3d trajectory' in line:
                # get T/F value
                metadata['3d trajectory'] = get_boolean(line)
            elif 'forecast data' in line:
                # get T/F value
                metadata['forecast data'] = get_boolean(line)
            elif 'forward trajectory' in line:
                # get T/F value
                metadata['forward trajectory'] = get_boolean(line)
            else:
                # skip
                pass

    return metadata, count


def read_traj(filepath):

    metadata, end = process_metadata(filepath)

    # Assuming filename is of the form rtraj_mosaic_1min_YYYYmmdd00
    fn = os.path.basename(filepath).split('_')
    # traj_dt = dt.datetime.strptime(fn[-1], '%Y%m%d00')
    freq = fn[-2]  # or infer from number of trajectories?

    traj_dt = dt.datetime.strptime(metadata['trajectory base time'], '%Y%m%d%H')
    npart = metadata['total number of trajectories']

    # TODO get NTS from per trajectory metadata
    nts = 88

    # TODO get col_names from data
    metadata['attribute names'] = [ATTR[x] for x in metadata['attribute types']]
    col_names = ['STEP', 'HOURS', 'LAT', 'LON', 'P (MB)'] + metadata['attribute names']

    index_col = col_names[0]
    skip_rows = end + 1

    traj_list = [None]*npart
    with pd.read_csv(filepath,
                     skiprows=skip_rows,
                     delim_whitespace=True,
                     skipinitialspace=True,
                     header=0,
                     names=col_names,
                     index_col=index_col,
                     iterator=True) as reader:
        i = 0
        while i < npart:
            try:
                chunk = reader.get_chunk(nts+1)
                traj_list[i] = chunk
                reader.get_chunk(2)
            except StopIteration as e:
                break
            i = i+1
    # Combine reads, indexing by timestamp
    ts = dt.datetime.strftime(traj_dt, '%Y-%m-%d')
    df = pd.concat(traj_list,
                   keys=pd.date_range(ts, periods=npart, freq=freq),
                   names=['READ', index_col])
    return df, metadata


def read_data(input_dir, start_date, end_date=None):

    if not os.path.isdir(input_dir):
        err_msg = "Not a directory: {0}\n".format(input_dir)
        raise ValueError(err_msg)

    start_date = dt.datetime.fromisoformat(start_date)
    if end_date is not None:
        end_date = dt.datetime.fromisoformat(end_date)

    start_dir = os.getcwd()
    os.chdir(input_dir)

    files = [glob.glob(date.strftime("rtraj*%Y%m%d00"))
             for date in daterange(start_date, end_date)]
    files = [filename for elem in files for filename in elem]

    os.chdir(start_dir)

    data = [read_traj(os.path.join(input_dir, file)) for file in files]

    return data


def daterange(start_date, end_date=None):
    if end_date is None:
        end_date = start_date

    for n in range(int((end_date - start_date).days + 1)):
        yield start_date + dt.timedelta(n)


def main():

    filepath = parse_args()
    trajs = read_traj(filepath)
    print(trajs)

    # end main()


if __name__ == '__main__':
    main()
