import pandas as pd
import os
import datetime as dt
import numpy as np
import glob
import PySAM.Pvwattsv8 as pv
import shutil
import requests
import yaml
from utils import get_lat_long


class solar_generation:
    
    def __init__(self, location, solar_panel_specs, start_year, end_year, retries = 0, verbose = True, NSRDB = True):
        """Parameters
        ----------

        start_year : TYPE
            DESCRIPTION.
        end_year : TYPE
            DESCRIPTION.
        retries : TYPE, optional
            DESCRIPTION. The default is 0.
        verbose : TYPE, optional
            DESCRIPTION. The default is True.
        NSRDB : TYPE, optional
            DESCRIPTION. The default is True.

        Returns
        -------
        None.

        """
        self.location = location
        self.solar_panel_specs = solar_panel_specs
        self.directory = os.getcwd()
        self.start_year = start_year
        self.end_year = end_year
        self.nrel_creds = yaml.load(open('./nrel_credentials.yaml'), Loader=yaml.Loader)
        self.nrel_user = self.nrel_creds['username']
        self.nrel_key = self.nrel_creds['key']
        try:
            os.mkdir('CSV_SOLAR_DATA')
        except:
            pass
        try:
            os.mkdir('Solar_Results')
        except:
            pass
        #Try to create an archive directory in the results directory. Then move any existing results
        #If it already exists move any result files into the directory
        try:
            os.mkdir(os.path.join(os.path.join(self.directory, 'Solar_Results'), 'Archive'))
            _ = [shutil.move(file, os.path.join(os.path.join('Solar_Results', 'Archive'), file.split('/')[1])) for file in glob.glob(os.path.join('Solar_Results', '*.csv'))]
        except:
            _ = [shutil.move(file, os.path.join(os.path.join('Solar_Results', 'Archive'), file.split('/')[1])) for file in glob.glob(os.path.join('Solar_Results', '*.csv'))]
        #Same story for any existing radiation data files
        try:
            os.mkdir(os.path.join('CSV_SOLAR_DATA', 'Archive'))
        except:
            _ = [shutil.move(file, os.path.join(os.path.join('CSV_SOLAR_DATA', 'Archive'), file.split('/')[1])) for file in glob.glob(os.path.join('CSV_SOLAR_DATA', '*.csv'))]
    
    def pull_solar_data(self, lat, long, year, leap='true', utc='true'):
        '''lat = latitude, long = longitude, site = site name, year = year, leap if you want to pull leap year, needs to be a string, utc should be false.
        This is because SAM requires that the solar data be in local time zone. This function reads the data from the API and writes a csv. It returns the file name
        for use in the PVWatts model. 
        '''
        solar_data_loc = os.path.join(self.directory, 'CSV_SOLAR_DATA')
        # Set the attributes to extract (e.g., dhi, ghi, etc.), separated by commas.
        attributes = 'ghi,dhi,dni,wind_speed,air_temperature,solar_zenith_angle,dew_point,wind_direction,relative_humidity,surface_pressure,surface_albedo'
        interval = '60'
        url = f'https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-2-2-download.csv?wkt=POINT({long}%20{lat})&names={year}&leap_day={leap}&interval={interval}&utc={utc}&email={self.nrel_user}&api_key={self.nrel_key}&attributes={attributes}'
        #Request the data from the API
        data = requests.get(url)
        data = data.text
        tries = 0
        #While the api fails try again, but only 10 times
        while data.find('Not Found') > -1 or data.find('Data processing failure') > -1 or data.lower().find('error') > -1 and tries <=10:
            #Iterate the counter
            tries +=1
            #Print the error message
            print(f'API failure for year {year}, adjusting long from {long} to {long -0.01} and retrying. Retry #{tries}')
            #Adjust the longitude
            long = long-0.01
            #Redefine the URL
            base_api = f'https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-2-2-download.csv?wkt=POINT({long}%20{lat})&names={year}&leap_day={leap}&interval={interval}&utc={utc}&email={self.nrel_user}&api_key={self.nrel_key}&attributes={attributes}'
            data = requests.get(base_api)
            data = data.text
        #Write the data as a csv in the proper location
        file_name = os.path.join(solar_data_loc, f'{year}_solar_radiation_file.csv')
        with open(file_name, 'a+') as fp:
            fp.write(data)
        return file_name
    
    def solar_generation(self, year):
        """This function calls PVWatts7 for each facility in the input file. It only needs a the site details and the year for the weather data.
        The function returns a simulated 8760 for the site and the year. 
        """
        
        #Define the system
        system_design = {'array_type': int(self.solar_panel_specs['array_type']),\
                         'azimuth': float(self.solar_panel_specs['azimuth']),\
                         'tilt': float(self.solar_panel_specs['tilt']),\
                         'system_capacity': float(self.solar_panel_specs['system_capacity']),\
                         'dc_ac_ratio': float(self.solar_panel_specs['dc_ac_ratio']),\
                         'module_type':0}
    
        pv_model = pv.default('PVWattsNone')
        #Set system design
        pv_model.SystemDesign.assign(system_design)
        #Set the weather file using the pull_solar_data function
        lat,long = get_lat_long(self.location)
        pv_model.SolarResource.solar_resource_file = self.pull_solar_data(lat = lat, long = long, year = year, leap = 'true', utc = 'true')
        #Execute the model
        pv_model.execute()
        #return the ac output
        return pv_model.Outputs.ac
    
    def generate_profiles(self):
        errors = {}
        solar_dict = {}
        for year in range(self.start_year, self.end_year + 1):
            if year == self.start_year:
                solarGenDf = pd.DataFrame(self.solar_generation( year = year), columns = ['Generation'])
            else:
                simulation = pd.DataFrame(self.solar_generation( year = year), columns = ['Generation'])
                simulation['year'] = year
                solar_dict[year] = simulation
                solarGenDf = pd.concat([solarGenDf, solar_dict[year]])
        outpath = os.path.join('Solar_Results', 'solar_generation.csv')
        solarGenDf.to_csv(outpath) 
        return outpath


def get_solar_profile(location,solar_panel_specs):
    start_year = 2022
    end_year = 2022
    solar = solar_generation(location,solar_panel_specs, start_year = start_year, end_year = end_year)
    solar_file = solar.generate_profiles()
    return solar_file








