import requests
import pytz
from datetime import datetime,timezone
import os
import difflib
import requests
import pandas as pd


def get_lat_long(address):
    api_key = '66ba4fe7c5a98565166069csta691ce'
    address=address
    url = f'https://geocode.maps.co/search?q={address}&api_key={api_key}'
    response = requests.get(url)
    data = response.json()[0]
    lat = data['lat']
    lon = data['lon']
    return lat,lon
    
def add_reqd_output(idf_file):

    lines_to_add = [
    'Output:Meter:MeterFileOnly,Electricity:Facility,hourly;',
    'Output:Meter:MeterFileOnly,Electricity:HVAC,hourly;'
    'Output:Variable,*,Facility Total Building Electricity Demand Rate,Hourly;'
    'Output:Variable,*,Facility Total HVAC Electricity Demand Rate,Hourly;'
     ]

    with open(idf_file, 'r') as file:
        idf_content = file.readlines()
        
    last_output_index = -1
    for i, line in enumerate(idf_content):
        if line.startswith('Output:Variable'):
            last_output_index = i

    if last_output_index != -1:
        idf_content.insert(last_output_index + 1, '\n')  # add a blank line for readability
        idf_content.insert(last_output_index + 2, lines_to_add[0] + '\n')
        idf_content.insert(last_output_index + 3, lines_to_add[1] + '\n')

    with open(idf_file, 'w') as file:
        file.writelines(idf_content)


def change_reporting_frequency(idf_file):
  
    with open(idf_file, 'r') as f:
        lines = f.readlines()

    # Define the meters to change
    meters_to_change = ['Electricity:Facility', 'Electricity:HVAC']

    # Iterate through lines and modify the reporting frequency
    for i in range(len(lines)):
        line = lines[i].strip()
        if line.startswith('Output:Meter:MeterFileOnly'):
            for meter in meters_to_change:
                if meter in line:
                    # Change 'monthly' to 'hourly'
                    lines[i] = line.replace('monthly', 'hourly') + '\n'
                    break
        if len(line) >= 3 and line[1] == 'Floor' and line[2] == 'Area':
            lines[i] = line.replace('232.25', '92.903') + '\n'
            


    # Write the modified content back to the IDF file
    with open(idf_file, 'w') as f:
        f.writelines(lines)

    
def convert_utc_to_pt(hour):
    if hour>=8:
        hour-=8
    else:
        hour+=16
    return hour

    


def get_month(df):
    if 0<= df['Day']<=30:
        return 1
    if 31<= df['Day']<=58:
        return 2
    if 59<= df['Day']<=89:
        return 3
    if 90<=df['Day']<=119:
        return 4
    if 120<= df['Day']<=150:
        return 5
    if 151<= df['Day']<=180:
        return 6
    if 181<=df['Day']<=211:
        return 7
    if 212<= df['Day']<=242:
        return 8
    if 243<= df['Day']<=272:
        return 9
    if 273<= df['Day']<=303:
        return 10
    if 304<=df['Day']<=333:
        return 11
    if 334<=df['Day']<=364:
        return 12
    
def get_days(df):
  if df['Month'] == 4 or df['Month'] == 6 or df['Month'] == 9:
    return 30
  elif df['Month'] == 2:
    return 28
  else:
    return 31
  

def add_missing_tiers(dict):
    tiers = ['summer_peak','summer_off_peak','winter_peak','winter_off_peak']
    for key in dict:
        if len(dict[key].keys())!=4:
            missing_tiers = [x for x in tiers if x not in dict[key].keys() ]
            for tier in missing_tiers:
                dict[key][tier] = 0
    return dict


def get_weather_file(folder_path, user_input):
    files = os.listdir(folder_path)
    user_input = 'USA_CA_' + user_input + '_TMY.epw'
    matches = difflib.get_close_matches(user_input, files, n=1, cutoff=0.6)
    if not matches:
        print(f"No matching file found for '{user_input}'.")
        return None
    best_match = matches[0]
    file_path = os.path.join(folder_path, best_match)
    return file_path


def get_empty_dict():
    battery_dict = {'Tesla Powerwall - 13.5kWh':0, 'Ecoflow DPU + Smart Home Panel-6kwh':0, 'Anker Solix X1-3kwh':0,'Generac PWRcell-9kwh':0,'Enphase IQ Battery 10T-10kwh':0 }
    dict = {x: {} for x in battery_dict}
    for key in dict:
        dict[key] = {x:{} for x in range(1,13)}
        tiers = ['summer_peak','summer_off_peak', 'summer_mid_peak', 'winter_peak','winter_off_peak', 'winter_mid_peak']
        for key1 in dict[key]:
            dict[key][key1] = {x:0 for x in tiers}
    return dict


def convert_to_df(battery_dict):
    df_data = []
    for battery_type, battery_data in battery_dict.items():
        for month in range(1, 13):
            for tou_period, load in battery_data[month].items():
                df_data.append([battery_type, month, tou_period, load])
    columns = ['Battery_Type', 'Month', 'TOU_Period', 'Load']
    df = pd.DataFrame(df_data, columns=columns)
    return df

def dicts_to_df(load_dict, export_dict):
    df = pd.DataFrame.from_dict(load_dict, orient='index')
    df['Month'] = df.index
    df_load = df.melt(id_vars='Month', var_name='TOU_Period', value_name='Solar_Load')
    df1 = pd.DataFrame.from_dict(export_dict, orient='index')
    df1['Month'] = df1.index
    df_export = df1.melt(id_vars='Month', var_name='TOU_Period', value_name='Solar_Export')
    return df_load, df_export

def get_battery_num_df(num_dict):
    df = pd.DataFrame([num_dict])
    df = df.melt(var_name='Battery_Type', value_name='No_Batteries')
    return df

def get_capacity(battery_type):
    capacity = battery_type.split('-')
    round_trip_efficiency = 0.9
    for i in range(len(capacity[1])):
        if capacity[1][i] == 'k':
            index = i
            capacity[1] = capacity[1][:index]
            return round_trip_efficiency*float(capacity[1])
        
def get_pricing_plan(date):
    if date == 'before_april_2023':
        return 'NEM'
    if date == 'after_april_2023':
        return 'NBT'
    
def get_timestamp_month(timestamp):
    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    return dt.month

def get_timestamp_day(timestamp):
    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    return dt.day

def get_timestamp_hour(timestamp):
    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
    return dt.hour


def day_of_year(df):
    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    cumulative_days_before_month = [0] + [sum(days_in_month[:i]) for i in range(1, 12)]
    month = df['Month']
    day = df['Day']
    return cumulative_days_before_month[month - 1] + day - 1
    
        
def get_num_dict(batteries,comp_dict):
    battery_dict = {'Tesla Powerwall - 13.5kWh':0, 'Ecoflow DPU + Smart Home Panel-6kwh':0, 'Anker Solix X1-3kwh':0,'Generac PWRcell-9kwh':0,'Enphase IQ Battery 10T-10kwh':0 }
    num_dict = {}
    for battery in battery_dict:
        num_dict[battery] = int(batteries)*(float(comp_dict[battery])/100)
    return num_dict

def flatten_hourly_dict(hourly_dict, solar_shift_dict):
    data = []
    df = pd.read_csv('original_hourly_load.csv')

    for day, hours in hourly_dict.items():
        for hour, value in hours.items():
            data.append([day, hour, value])
    df_shifted = pd.DataFrame(data, columns=['Day', 'Hour', 'Paired_Change'])

    for day, hours in solar_shift_dict.items():
        for hour, value in hours.items():
            data.append([day, hour, value])
    solar_shifted = pd.DataFrame(data, columns=['Day', 'Hour', 'Solar_Change'])

    df_final = df.merge(df_shifted, on=['Day','Hour'])
    #df_final = df_final.merge(solar_shifted, on=['Day','Hour'])
    df_final['Paired_Load'] = df_final['Load'] + df_final['Paired_Change']
    #df_final['Solar_Load'] = df_final['Load'] + df_final['Solar_Change']
    df_final.to_csv(os.path.join(os.getcwd(),'final_hourly_load.csv'))





    

    




