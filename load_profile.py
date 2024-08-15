from eppy import modeleditor
from eppy.modeleditor import IDF
import os
import pandas as pd


def run_energyplus_simulation(idf_path, weather_path):
    """
    Function to run the energyplus simulation which gives the hourly load profiles based on Weather and Building Data.
    Weather files need to be in .epw format and building files need to be in .idf format
    
    """
    idd_file = 'C:\EnergyPlusV9-5-0\Energy+.idd'
    IDF.setiddname(idd_file)
    idf = IDF(idf_path)
    idf.epw = weather_path
    out_dir = os.path.join(os.getcwd(),'output')
    idf.run(output_directory=out_dir, readvars=True, annual=True)
    # eplusmtr.csv file has the hourly load profiles for the entire year
    out_file = os.path.join(out_dir, 'eplusmtr.csv')
    return out_file

    




