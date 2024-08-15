import pandas as pd
import numpy as np
import os
import copy
from utils import get_empty_dict, convert_to_df,get_capacity, get_timestamp_month, get_timestamp_day, get_timestamp_hour, day_of_year, convert_utc_to_pt, get_num_dict, dicts_to_df, get_battery_num_df, get_month
from generation_profile import get_solar_profile

BATTERY_dict = {'Tesla_Powerwall': {'capacity':13.5 , 'hourly_discharge':3.375 , 'max_discharge_rate':11.5},
                'Ecoflow': {'capacity': 6, 'hourly_discharge': 1.5 }, 'Anker_Solix':{'capacity':3, 'hourly_discharge':0.75}, 'Generac_PWRcell': {'capacity':9, 'hourly_discharge':2.25},'Enphase_IQ':{'capacity':10, 'hourly_discharge':2.5}}

class GridImpact():
    def __init__(self, load_file, batteries,composition, county):
        self.load_file = 'Item17_res_sample_000000000005.csv'
        self.batteries = batteries
        self.composition = composition
        self.county = county

    def run(self):
        self.get_generation_profile()
        load_df = self.get_updated_load_profile()
        paired_df = self.get_final_load_changes(load_df)
        solar_df, export_df = self.get_solar_reduction()
        system_df = self.get_system_load()
        table_html = self.get_grid_impact(paired_df, solar_df,export_df, system_df)
        return table_html

    def get_load_profile(self, load_file):
        #load_df = pd.read_csv(load_file)
        #load_df['Month'] = load_df['Datetime_HE'].apply(get_timestamp_month)
        #load_df['Day'] = load_df['Datetime_HE'].apply(get_timestamp_day)
        #load_df['Hour'] = load_df['Datetime_HE'].apply(get_timestamp_hour)
        #load_df['Day_of_Year'] = load_df.apply(day_of_year,axis=1)
        #load_df = load_df.groupby(['Month','Day_of_Year', 'Hour'])['KWH'].median().reset_index()
        #load_df = load_df.groupby(['Month','Day_of_Year', 'Hour'])['KWH'].mean().reset_index()
        #load_df['Season'] = np.where((load_df['Day_of_Year'] >= 151) & (load_df['Day_of_Year'] <= 272), 'summer', 'winter')
        #load_df['Pricing'] = np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 19), 'peak', 'off_peak')
        #load_df = load_df[['Hour','KWH','Day_of_Year','Month','Season','Pricing']]
        #load_df = load_df.rename(columns={'Day_of_Year': 'Day', 'KWH':'Load'})

        load_df = pd.read_csv('load_output.csv')
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        load_df['Month'] = load_df.apply(get_month,axis=1)
        load_df['Season'] = np.where((load_df['Day'] >= 151) & (load_df['Day'] <= 272), 'summer', 'winter')
        load_df['Pricing'] = np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 19), 'peak', 'off_peak')


        daily_load = load_df.groupby('Day')['Load'].sum().reset_index()
        daily_load = daily_load.rename(columns={'Load': 'daily_load'})
        median_df = load_df[['Month','Day','Hour','Load']]
        median_df.to_csv(os.path.join(os.getcwd(), 'median_load_profile.csv'))
        
        #df_load = pd.read_csv(load_file)
        #df_load['Month'] = df_load['Datetime_HE'].apply(get_timestamp_month)
        #df_load['Day'] = df_load['Datetime_HE'].apply(get_timestamp_day)
        #df_load['Hour'] = df_load['Datetime_HE'].apply(get_timestamp_hour)
        #df_load['Day_of_Year'] = df_load.apply(day_of_year,axis=1)
        #df_load = df_load.groupby(['Month','Day_of_Year', 'Hour'])['KWH'].mean().reset_index()
        #df_load['Season'] = np.where((df_load['Day_of_Year'] >= 151) & (df_load['Day_of_Year'] <= 272), 'summer', 'winter')
        #df_load['Pricing'] = np.where((df_load['Hour'] >= 16) & (df_load['Hour'] <= 19), 'peak', 'off_peak')
        #df_load = df_load[['Hour','KWH','Day_of_Year','Month','Season','Pricing']]
        #df_load = df_load.rename(columns={'Day_of_Year': 'Day', 'KWH':'Load'})
        #avg_df = df_load[['Month','Day','Hour','Load']]
        #avg_df.to_csv(os.path.join(os.getcwd(), 'avg_load_profile.csv'))


        peak_df = load_df[(load_df['Hour'] >= 16) & (load_df['Hour'] <= 19)]
        peak_df = peak_df.groupby(['Month', 'Season','Day'])['Load'].sum().reset_index()
        peak_df = peak_df.rename(columns = {'Load':'peak_load'})
        peak_df = peak_df.merge(daily_load, on='Day')
        solar_df = pd.read_csv('gi_solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        gen_df = solar_df.groupby('Day')['Generation'].sum().reset_index()
        gen_df = gen_df.rename(columns = {'Generation':'solar_generation'})
        merged_df = peak_df.merge(gen_df, on='Day')
        merged_df.to_csv(os.path.join(os.getcwd(), 'grid_impact_load_profile.csv'))
        return merged_df
    
    def get_updated_load_profile(self):
        
        solar_df = pd.read_csv('gi_solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        solar_df['Hour'] = solar_df['Hour'].apply(convert_utc_to_pt)
        load_df = pd.read_csv('load_output.csv')
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        load_df['Month'] = load_df.apply(get_month,axis=1)
        load_df.to_csv(os.path.join(os.getcwd(), 'median_load_profile.csv'))
        merged_df = solar_df.merge(load_df, on = ['Day','Hour'])
        merged_df['Season'] = np.where((merged_df['Day'] >= 151) & (merged_df['Day'] <= 272), 'summer', 'winter')
        merged_df['day_of_week'] = (merged_df['Day'] % 7)
        merged_df['Weekend'] = merged_df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)
        merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        merged_df['Month'] = merged_df.apply(get_month,axis=1)
        merged_df = merged_df[['Hour', 'Day','Weekend', 'Season', 'Load','Generation','Pricing','Month']]
        merged_df = merged_df.rename(columns = {'Load':'hourly_load', 'Generation':'hourly_generation'})
        
        solar_df = pd.read_csv('gi_solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        solar_df['Hour'] = solar_df['Hour'].apply(convert_utc_to_pt)
        load_df = pd.read_csv('load_output.csv')
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        comb_df = solar_df.merge(load_df, on = ['Day','Hour'])
        comb_df = comb_df[['Hour', 'Day', 'Load','Generation']]
        comb_df['Gen_Hour'] = np.where(comb_df['Generation'] > 0, 1, 0)
        gen_df = comb_df[comb_df['Hour'] <=15]
        gen_df = gen_df.groupby('Day')[['Generation','Gen_Hour']].sum().reset_index()
        daily_load = comb_df.groupby('Day')['Load'].sum().reset_index()
        daily_load = daily_load.rename(columns={'Load': 'daily_load'})
        load_df = comb_df[(comb_df['Hour'] >= 16) & (comb_df['Hour'] <= 20)]
        load_df = load_df.groupby('Day')['Load'].sum().reset_index()
        final_df = gen_df.merge(load_df, on = 'Day')
        final_df = final_df.merge(daily_load, on='Day')
        final_df = final_df.rename(columns = {'Load':'peak_load', 'Generation':'solar_generation'})
        battery_df = final_df.merge(merged_df, on='Day')
        sorted_df = battery_df.sort_values(by=['Day','Hour'])
        return sorted_df
    

    def get_generation_profile(self):
        
        solar_panel_specs = {'array_type': 1,
                         'azimuth': 180,\
                         'tilt': 25,\
                         'system_capacity': 4,\
                         'dc_ac_ratio': 1.4,\
                         'module_type':0}
        solar_file = get_solar_profile(self.county,solar_panel_specs)
        solar_df = pd.read_csv(solar_file,header=0)
        solar_df['Hour'] = range(len(solar_df))
        solar_df['Generation'] =  solar_df['Generation']/1000
        solar_df = solar_df[['Hour','Generation']]
        solar_df = solar_df[solar_df['Hour'] <=8759]
        solar_df.to_csv(os.path.join(os.getcwd(),'gi_solar_output.csv'),header=True)



    
    def get_updated_load_changes(self, df):
        load_dict = get_empty_dict()
        export_dict = copy.deepcopy(load_dict)
        batt_charged = {x:0 for x in range(365)}
        battery_dict = {'Tesla Powerwall - 13.5kWh':0, 'Ecoflow DPU + Smart Home Panel-6kwh':0, 'Anker Solix X1-3kwh':0,'Generac PWRcell-9kwh':0,'Enphase IQ Battery 10T-10kwh':0 }
        for battery in battery_dict:
            eff_capacity = get_capacity(battery)
            for i in range(len(df)):
                solar_generation = df.loc[i,'solar_generation']
                peak_load = df.loc[i,'peak_load']
                season = df.loc[i,'Season']
                month = df.loc[i,'Month']
                daily_load = df.loc[i,'daily_load']
                off_peak_load = daily_load-peak_load
                weekend = df.loc[i,'Weekend']
                hourly_generation = df.loc[i,'hourly_generation']
                hourly_load = df.loc[i,'hourly_load']
                pricing = df.loc[i,'Pricing']
                hour = df.loc[i,'Hour']
                gen_hours = df.loc[i,'Gen_Hour']
                if peak_load <= eff_capacity and solar_generation >= peak_load:
                    if pricing == 'off_peak':
                        amount_charging = peak_load
                        hourly_charging = peak_load/ gen_hours
                        hourly_generation = max(0, hourly_generation-hourly_charging)
                        if hourly_generation < hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                        if hourly_generation > hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                            export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load

        
                    if pricing =='peak' or pricing == 'mid_peak':
                        if hourly_generation < hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                        if hourly_generation > hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                            export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load

                    if hour == 17:   
                        load_dict[battery][month][f'{season}_{pricing}'] -= peak_load
        
                if solar_generation < peak_load and eff_capacity>=peak_load:
                    if hour == 17:   
                        load_dict[battery][month][f'{season}_{pricing}'] -= peak_load
                        load_dict[battery][month][f'{season}_off_peak'] += peak_load-solar_generation

                if eff_capacity < peak_load and solar_generation > eff_capacity:
                    if pricing == 'off_peak':
                        amount_charging = eff_capacity
                        hourly_charging = eff_capacity/ gen_hours
                        hourly_generation = max(0, hourly_generation-hourly_charging)
                        if hourly_generation < hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                        if hourly_generation > hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                            export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
        
                    if pricing =='peak' or pricing == 'mid_peak':
                        if hourly_generation < hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                        if hourly_generation > hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                            export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load

                    if hour == 17:   
                        load_dict[battery][month][f'{season}_{pricing}'] -= eff_capacity
        
                if eff_capacity < peak_load and solar_generation < eff_capacity:
                    if hour == 17:   
                        load_dict[battery][month][f'{season}_{pricing}'] -= eff_capacity
                        load_dict[battery][month][f'{season}_off_peak'] += eff_capacity-solar_generation

        load_change_df = convert_to_df(load_dict)
        export_df = convert_to_df(export_dict)
        export_df = export_df.rename(columns={'Load':'Export'})
        merged_df = load_change_df.merge(export_df, on=['Battery_Type','Month','TOU_Period'])
        return merged_df
    

    def get_final_load_changes(self, df):
        load_dict = get_empty_dict()
        export_dict = copy.deepcopy(load_dict)
        batt_charged = {x:0 for x in range(365)}
        battery_dict = {'Tesla Powerwall - 13.5kWh':0, 'Ecoflow DPU + Smart Home Panel-6kwh':0, 'Anker Solix X1-3kwh':0,'Generac PWRcell-9kwh':0,'Enphase IQ Battery 10T-10kwh':0 }
        for battery in battery_dict:
            eff_capacity = get_capacity(battery)/(0.9)
            for index, row in df.iterrows():
                solar_generation = row['solar_generation']
                peak_load = row['peak_load']
                season = row['Season']
                month = row['Month']
                daily_load = row['daily_load']
                off_peak_load = daily_load-peak_load
                weekend = row['Weekend']
                hourly_generation = row['hourly_generation']
                hourly_load = row['hourly_load']
                pricing = row['Pricing']
                hour = row['Hour']
                day = row['Day']
                max_hourly_charge = 20
                max_hourly_discharge = 20
                if solar_generation >= eff_capacity:
                    if pricing == 'off_peak':
                        if batt_charged[day] < eff_capacity:
                            batt_charged[day] += min(hourly_generation, max_hourly_charge)
                            if batt_charged[day] < eff_capacity:
                                if hourly_generation > max_hourly_charge:
                                    hourly_generation -= max_hourly_charge
                                    if hourly_generation < hourly_load:
                                        load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                                    if hourly_generation > hourly_load:
                                        load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                                        export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                            if batt_charged[day] > eff_capacity:
                                excess = batt_charged[day]-eff_capacity
                                batt_charged[day]-=excess
                                if hourly_generation >= max_hourly_charge:
                                    hourly_generation -= max_hourly_charge
                                    hourly_generation+= excess
                                if hourly_generation < max_hourly_charge:
                                    hourly_generation = excess
                                if hourly_generation < hourly_load:
                                    load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                                if hourly_generation > hourly_load:
                                    load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                                    export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                                continue
                        if batt_charged[day] == eff_capacity:
                            if hourly_generation < hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                            if hourly_generation > hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                                export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load


        
                    if pricing =='peak' or pricing == 'mid_peak':
                        if hour==16:
                            batt_charged[day] = 0.9*batt_charged[day]
                        if hourly_generation <= hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                            eff_hourly_load = hourly_load-hourly_generation
                        if hourly_generation > hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                            export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                            eff_hourly_load=0
          
                        if batt_charged[day] > 0:
                            if batt_charged[day] >= eff_hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
                                batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
                            if batt_charged[day] < eff_hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= batt_charged[day]
                                batt_charged[day]=0
          
                        if hour==19 and batt_charged[day] > 0:
                            export_dict[battery][month][f'{season}_{pricing}'] -= batt_charged[day]
                            batt_charged[day]=0
            


                if solar_generation < eff_capacity:
                    if pricing == 'off_peak':
                        if batt_charged[day] < solar_generation:
                            batt_charged[day] += min(hourly_generation, max_hourly_charge)
                            if batt_charged[day] < solar_generation:
                                if hourly_generation > max_hourly_charge:
                                    hourly_generation -= max_hourly_charge
                                    if hourly_generation < hourly_load:
                                        load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                                    if hourly_generation > hourly_load:
                                        load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                                        export_dict[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                            if batt_charged[day] > solar_generation:
                                excess = batt_charged[day]-solar_generation
                                batt_charged[day]-=excess
                                if hourly_generation >= max_hourly_charge:
                                    hourly_generation -= max_hourly_charge
                                    hourly_generation+= excess
                                if hourly_generation < max_hourly_charge:
                                    hourly_generation = excess
                                if hourly_generation < hourly_load:
                                    load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                                if hourly_generation > hourly_load:
                                    load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                                    export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                                continue
                        if batt_charged[day] == solar_generation:
                            if hourly_generation < hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                            if hourly_generation > hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                                export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
          
                            if hour == 10:
                                load_dict[battery][month][f'{season}_{pricing}'] += eff_capacity-solar_generation
                                batt_charged[day] += eff_capacity-solar_generation

        
                    if pricing =='peak' or pricing == 'mid_peak':
                        if hour==16:
                            batt_charged[day] = 0.9*batt_charged[day]
                        if hourly_generation <= hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation
                            eff_hourly_load = hourly_load-hourly_generation
                        if hourly_generation > hourly_load:
                            load_dict[battery][month][f'{season}_{pricing}'] -= hourly_load
                            export_dict[battery][month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                            eff_hourly_load = 0
                        if batt_charged[day] > 0:
                            if batt_charged[day] >= eff_hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
                                batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
                            if batt_charged[day] < eff_hourly_load:
                                load_dict[battery][month][f'{season}_{pricing}'] -= batt_charged[day]
                                batt_charged[day]=0
                        if hour==19 and batt_charged[day] > 0:
                            export_dict[battery][month][f'{season}_{pricing}'] -= batt_charged[day]
                            batt_charged[day]=0
        
        load_change_df = convert_to_df(load_dict)
        export_df = convert_to_df(export_dict)
        export_df = export_df.rename(columns={'Load':'Export'})
        merged_df = load_change_df.merge(export_df, on=['Battery_Type','Month','TOU_Period'])
        return merged_df
        
    

    
    def get_solar_reduction(self):
        df = pd.read_csv('median_load_profile.csv')
        solar_df = pd.read_csv('gi_solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        solar_df['Hour'] = solar_df['Hour'].apply(convert_utc_to_pt)
        solar_df['Season'] = np.where((solar_df['Day'] >= 151) & (solar_df['Day'] <= 272), 'summer', 'winter')
        solar_df['day_of_week'] = (solar_df['Day'] % 7)
        solar_df['Weekend'] = solar_df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)
        solar_df['Pricing'] = np.where((solar_df['Hour'] >= 16) & (solar_df['Hour'] <= 20) & (solar_df['Weekend'] == 0),
            'peak',
            np.where((solar_df['Hour'] >= 16) & (solar_df['Hour'] <= 20) & (solar_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        df = df.merge(solar_df, on=['Day','Hour'])
        df = df.rename(columns= {'Load':'hourly_load', 'Generation':'hourly_generation'})
        export_dict = {x:{} for x in range(1,13)}
        tiers = ['summer_peak','summer_off_peak', 'summer_mid_peak', 'winter_peak','winter_off_peak','winter_mid_peak']
        for key in export_dict:
            export_dict[key] = {x:0 for x in tiers}
        load_dict = copy.deepcopy(export_dict)
        for i in range(len(df)):
            hourly_generation = df.loc[i,'hourly_generation']
            hourly_load = df.loc[i,'hourly_load']
            season = df.loc[i,'Season']
            pricing = df.loc[i,'Pricing']
            month = df.loc[i,'Month']
            if hourly_generation < hourly_load:
                load_dict[month][f'{season}_{pricing}'] -= hourly_generation
            if hourly_generation > hourly_load:
                load_dict[month][f'{season}_{pricing}'] -= hourly_load
                export_dict[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
        load_df,export_df = dicts_to_df(load_dict, export_dict)
        return load_df,export_df
    
    def get_system_load(self):
        df = pd.read_csv('median_load_profile.csv')
        adoption_rate = 0.1
        total_meters = float(self.batteries)/adoption_rate
        df['Load'] = df['Load']*total_meters
        df['day_of_week'] = (df['Day'] % 7)
        df['Weekend'] = df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)
        df['Pricing'] = np.where((df['Hour'] >= 16) & (df['Hour'] <= 20) & (df['Weekend'] == 0),
            'peak',
            np.where((df['Hour'] >= 16) & (df['Hour'] <= 20) & (df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        df['Season'] = np.where((df['Day'] >= 151) & (df['Day'] <= 272), 'summer', 'winter')
        df = df.groupby(['Month','Season','Pricing'])['Load'].sum().reset_index()
        load_dict = {x:{} for x in range(1,13)}
        tiers = ['summer_peak','summer_off_peak','summer_mid_peak','winter_peak','winter_off_peak','winter_mid_peak']
        for key in load_dict:
            load_dict[key] = {x:0 for x in tiers}
        for i in range(len(df)):
            month = df.loc[i,'Month']
            pricing = df.loc[i,'Pricing']
            season = df.loc[i,'Season']
            load = df.loc[i,'Load']
            load_dict[month][f'{season}_{pricing}'] = load 
        df_system = pd.DataFrame.from_dict(load_dict, orient='index')
        df_system['Month'] = df_system.index
        df_pivot = df_system.melt(id_vars='Month', var_name='TOU_Period', value_name='System_Load')
        return df_pivot
        
    
    
    
    def get_grid_impact(self,paired_df, load_df, export_df, system_df):

        final_df = paired_df.merge(load_df, on=['Month','TOU_Period'])
        final_df = final_df.merge(export_df, on=['Month','TOU_Period'])
        final_df['Load_Shift'] = final_df['Load']+final_df['Export']- (final_df['Solar_Load'] + final_df['Solar_Export'])
        num_dict = get_num_dict(self.batteries,self.composition)
        comp_df = get_battery_num_df(num_dict)
        final_df = final_df.merge(comp_df, on='Battery_Type')
        final_df['Grid_Impact'] = final_df['Load_Shift']*final_df['No_Batteries']
        final_df.to_csv(os.path.join(os.getcwd(), 'grid_impact_battery.csv'))
        monthly_df = final_df.groupby(['Month','TOU_Period'])['Grid_Impact'].sum().reset_index()
        monthly_df = monthly_df.merge(system_df, on=['Month', 'TOU_Period'])
        monthly_df['% Change'] = (monthly_df['Grid_Impact']/monthly_df['System_Load'])*100
        monthly_df.to_csv(os.path.join(os.getcwd(), 'grid_impact_monthly.csv'))
        seasonal_df = monthly_df.groupby('TOU_Period')[['Grid_Impact','System_Load']].mean().reset_index()
        seasonal_df['% Change'] = (seasonal_df['Grid_Impact']/seasonal_df['System_Load'])*100
        seasonal_df = seasonal_df.rename(columns= {'TOU_Period': 'TOU Period','Grid_Impact':'Grid Impact', 'System_Load': 'System Load'})
        seasonal_df.to_csv(os.path.join(os.getcwd(), 'grid_impact_seasonal.csv'))
        table_html = seasonal_df.to_html(index=False)
        return table_html





   

