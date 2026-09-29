# -*- coding: utf-8 -*-
# Copied from rIACI 1.0.0, inst/python/data_processing.py (GPL-3).
import xarray as xr
import pandas as pd
import numpy as np
import os

def process_data(input_dir, output_dir, save_merged=False):
    """
    Processes ERA5-Land ARCO NetCDF files and saves daily grid-point values.

    ARCO ``tp`` contains hourly precipitation ending at its time stamp. Thus
    the value stamped 00:00 belongs to the preceding calendar day. The input
    must include 00:00 on the day after the last desired precipitation day.

    Parameters:
    - input_dir: str, directory containing input NetCDF files
    - output_dir: str, directory to save output files
    - save_merged: bool, optional, if True, saves the merged NetCDF file
    """
    import os
    import xarray as xr
    import numpy as np
    import pandas as pd

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    file_path = os.path.join(input_dir, '*.nc')
    
    # Open multiple NetCDF files as a single dataset
    data = xr.open_mfdataset(file_path, combine='by_coords')
    
    # Round longitude and latitude coordinates to one decimal place
    data.coords['longitude'] = np.round(data.coords['longitude'], 1)
    data.coords['latitude'] = np.round(data.coords['latitude'], 1)
    
    if save_merged:
        # Save the merged data
        merged_file = os.path.join(output_dir, 'merged_data.nc')
        data.to_netcdf(merged_file)
    
    # **Automatically detect the time coordinate and rename it to 'time'**
    # Try to find the coordinate with datetime type
    time_coords = []
    for coord in data.coords:
        if np.issubdtype(data.coords[coord].dtype, np.datetime64):
            time_coords.append(coord)
    
    # If no datetime coordinate found, look for coordinate names containing 'time'
    if not time_coords:
        for coord in data.coords:
            if 'time' in coord.lower():
                time_coords.append(coord)
    
    if not time_coords:
        raise ValueError("No time coordinate found in the dataset.")
    
    # Use the first time coordinate found
    time_coord = time_coords[0]
    
    # Ensure time coordinate is in datetime format
    data[time_coord] = pd.to_datetime(data[time_coord].values)
    
    # Rename the detected time coordinate to 'time'
    data = data.rename({time_coord: 'time'})
    
    # Perform calculations
    temperature = data.t2m - 273.15  # Convert temperature from Kelvin to Celsius
    precipitation = data.tp * 1000   # Convert precipitation from meters to millimeters
    precipitation = precipitation.assign_coords(time=precipitation.time - np.timedelta64(1, 'h'))
    daily_precipitation = precipitation.resample({'time': '1D'}).sum(skipna=False)
    hourly_precipitation_counts = precipitation.resample({'time': '1D'}).count()
    daily_precipitation = daily_precipitation.where(hourly_precipitation_counts == 24)
    windspeed = np.sqrt(data.u10**2 + data.v10**2)  # Calculate wind speed
    
    # Create a new dataset with the processed variables
    dataset = xr.Dataset({
        'TMAX': temperature.resample({'time': '1D'}).max(),  
        'TMIN': temperature.resample({'time': '1D'}).min(),  
        'PRCP': daily_precipitation,
        'WP': 0.5 * 1.23 * (windspeed.resample({'time': '1D'}).mean()**3)
    })
    
    # Save the processed dataset
    output_file = os.path.join(output_dir, 'processed_data.nc')
    dataset.to_netcdf(output_file)

def export_data_to_csv(nc_file, output_dir):
    """
    Exports selected data ('time', 'TMAX', 'TMIN', 'PRCP', 'WP') from a NetCDF file
    to CSV files, one for each latitude and longitude point, only if data is present.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Open the dataset
    ds = xr.open_dataset(nc_file)

    # Select only the required variables to speed up processing
    ds = ds[['time', 'TMAX', 'TMIN', 'PRCP', 'WP']]

    # Convert the dataset to a DataFrame and reset the index to include coordinate variables
    df = ds.to_dataframe().reset_index()

    # Group the DataFrame by latitude and longitude
    grouped = df.groupby(['latitude', 'longitude'])

    # Iterate over each group and save the data to a CSV file
    for (lat, lon), group in grouped:
        # Drop rows where all the selected variables are NaN
        group = group.dropna(subset=['TMAX', 'TMIN', 'PRCP', 'WP'], how='all')

        # If after dropping NaNs, the group is empty, skip it
        if group.empty:
            continue

        csv_filename = os.path.join(output_dir, f'{lat:.1f}_{lon:.1f}.csv')
        group.to_csv(csv_filename, index=False)

def csv_to_netcdf(csv_dir, output_file, freq):
    """
    Merges CSV files in a specified directory into a single NetCDF file, completing the grid by filling missing values.

    Parameters:
    csv_dir (str): Directory containing CSV files, each file representing a single latitude-longitude point.
                   The filename format should be 'lat_lon.csv'.
    output_file (str): Path to the output NetCDF file.
    freq (str): Frequency of the data, either 'monthly' or 'seasonal'.
                'monthly' data uses date format 'YYYY-MM';
                'seasonal' data uses date format like 'YYYY-SSS' (e.g., '1961-DJF').
    """
    data_list = []  # List to store data for each point
    lat_list = []
    lon_list = []
    time_set = set()

    # List all CSV files in the directory
    csv_files = [f for f in os.listdir(csv_dir) if f.endswith('.csv')]

    for csv_file in csv_files:
        # Extract latitude and longitude from the filename
        try:
            filename = os.path.splitext(csv_file)[0]  # Remove file extension
            lat_str, lon_str = filename.split('_')
            lat = float(lat_str)
            lon = float(lon_str)
        except ValueError:
            print(f"Filename format error, skipping file: {csv_file}")
            continue

        # Read the CSV file
        csv_path = os.path.join(csv_dir, csv_file)
        df = pd.read_csv(csv_path)

        # Rename 'Date' to 'time' for consistency and collect unique times
        df = df.rename(columns={"Date": "time"})
        time_set.update(df['time'].unique())

        # Add 'latitude' and 'longitude' columns
        df['latitude'] = lat
        df['longitude'] = lon

        # Convert DataFrame to xarray Dataset with 'time', 'latitude', 'longitude' as dimensions
        ds = df.set_index(['time', 'latitude', 'longitude']).to_xarray()

        data_list.append(ds)
        lat_list.append(lat)
        lon_list.append(lon)

    # Combine all single-point Datasets into one
    if data_list:
        # Get sorted lists of times, latitudes, and longitudes
        times = sorted(time_set)
        latitudes = sorted(set(lat_list))
        longitudes = sorted(set(lon_list))

        # Initialize an empty Dataset
        combined_ds = xr.Dataset(coords={'time': times, 'latitude': latitudes, 'longitude': longitudes})

        # Get data variable names
        data_vars = list(data_list[0].data_vars.keys())

        # Initialize data variables with NaN
        for var in data_vars:
            combined_ds[var] = (('time', 'latitude', 'longitude'),
                                np.full((len(times), len(latitudes), len(longitudes)), np.nan))

        # Build mapping from lat, lon, time to indices
        lat_to_idx = {lat: idx for idx, lat in enumerate(latitudes)}
        lon_to_idx = {lon: idx for idx, lon in enumerate(longitudes)}
        time_to_idx = {time: idx for idx, time in enumerate(times)}

        # For each dataset in data_list, assign data into combined_ds
        for ds in data_list:
            lat = ds.coords['latitude'].values.item()
            lon = ds.coords['longitude'].values.item()
            lat_idx = lat_to_idx[lat]
            lon_idx = lon_to_idx[lon]
            for var in data_vars:
                data_array = ds[var]
                # Get the time indices
                ds_times = data_array.coords['time'].values
                time_indices = [time_to_idx[t] for t in ds_times]
                combined_ds[var].values[np.ix_(time_indices, [lat_idx], [lon_idx])] = data_array.values.reshape(-1, 1, 1)

        # Save the combined data to a NetCDF file
        combined_ds.to_netcdf(output_file)
        print(f"Successfully merged CSV files into NetCDF file: {output_file}")
    else:
        print("No valid CSV files found, unable to create NetCDF file.")
