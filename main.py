import pandas as pd
import numpy as np
import os
import copy
import matplotlib.pyplot as plt
from load_profile import run_energyplus_simulation
from generation_profile import get_solar_profile
from savings import  get_updated_battery_savings, get_solar_savings, Billing
from utils import convert_utc_to_pt,get_month, get_weather_file, get_capacity, get_pricing_plan, flatten_hourly_dict
from rates import get_rates

class ProcessCustomerDetails():
    def __init__(self, address, iou,low_income_housing,battery_type,solar_data,interconnection_date,solar_pairing,array_type,azimuth,tilt,system_capacity,dc_ac_ratio,module_type,location,climate,tariff,load_file):
        self.address = address
        self.iou = iou
        self.low_income_housing = low_income_housing
        self.battery_type = battery_type
        self.solar_data = solar_data
        self.interconnection_date = interconnection_date
        self.solar_pairing = solar_pairing
        self.array_type = array_type
        self.azimuth = azimuth
        self.tilt = tilt
        self.system_capacity = system_capacity
        self.dc_ac_ratio = dc_ac_ratio
        self.module_type = module_type
        self.climate = climate
        self.weather_file = get_weather_file('weather_files', location)
        self.building_file = f'US+SF+CZ{self.climate}+gasfurnace+crawlspace+IECC_2021.idf'
        self.tariff = tariff
        self.load_file = load_file

    def run(self):
        solar_file = self.get_generation_profile()
        self.process_solar_data(solar_file)
        if self.load_file != '':
            load_file = 'customer_load.csv'
        else:
            load_data = self.get_load_profile()
            self.process_load_data(load_data)
            load_file = 'load_output.csv'
        plan = get_pricing_plan(self.interconnection_date)
        daily_df = self.updated_hourly_profiles(plan,load_file)
        load_dict = self.get_load_dict(plan,load_file)
        initial_load = self.get_delivery_profile(load_dict)
        initial_load.to_csv(os.path.join(os.getcwd(), 'initial_load.csv'))
        export_dict = self.get_export_dict()
        hourly_df = self.hourly_profiles(plan,load_file)
        solar_load,solar_export, solar_load_shift = get_solar_savings(hourly_df,load_dict,export_dict)
        solar_delivery = self.get_delivery_profile(solar_load)
        solar_delivery.to_csv(os.path.join(os.getcwd(), 'solar_load.csv'))
        solar_export = self.get_export_profile(solar_export)
        pricing_dict = get_rates(self.iou, self.tariff, plan)
        solar_obj = Billing(solar_delivery, solar_export, pricing_dict,plan)
        solar_bill = solar_obj.get_billing()
        savings = {}
        battery_dict = {'Tesla Powerwall-13.5kWh':0, 'Ecoflow DPU + Smart Home Panel-6kwh':0, 'Anker Solix X1-3kwh':0,'Generac PWRcell-9kwh':0,'Enphase IQ Battery 10T-10kwh':0 }
        plan = get_pricing_plan(self.interconnection_date)
        for battery in battery_dict:
            for year in range(0,5):
                eff_capacity = get_capacity(battery)/(0.9)
                eff_capacity = eff_capacity - 0.08*year*eff_capacity
                battery_load,battery_export,hourly_load_change = get_updated_battery_savings(daily_df,load_dict,export_dict,eff_capacity,plan)
                if battery ==self.battery_type:
                    flatten_hourly_dict(hourly_load_change, solar_load_shift)
                battery_delivery = self.get_delivery_profile(battery_load)
                battery_delivery.to_csv(os.path.join(os.getcwd(), 'paired_load.csv'))
                battery_export = self.get_export_profile(battery_export)
                battery_obj = Billing(battery_delivery, battery_export, pricing_dict,plan)
                battery_bill = battery_obj.get_billing()
                incremental_saving = solar_bill - battery_bill
                if year==0:
                    savings[battery] = {'incremental_saving': incremental_saving, 'battery_bill':battery_bill}
                battery_dict[battery] += incremental_saving
        for battery in battery_dict:
            battery_dict[battery] = battery_dict[battery]/5
        self.plot_battery_savings(battery_dict)
        battery_cost_dict = self.incentive_eligibility()
        break_even_dict = self.get_break_even_time(battery_cost_dict, battery_dict)
        self.plot_break_even_time(break_even_dict)
        break_even_time = break_even_dict[self.battery_type]
        self.plot_hourly_profiles()
        return [savings[self.battery_type]['incremental_saving'], savings[self.battery_type]['battery_bill'], solar_bill,break_even_time]
        

    
    def incentive_eligibility(self):
        battery_cost_dict = {'Tesla Powerwall-13.5kWh':13000, 'Ecoflow DPU + Smart Home Panel-6kwh':8700, 'Anker Solix X1-3kwh':10000,'Generac PWRcell-9kwh':19000,'Enphase IQ Battery 10T-10kwh':7200 }
        rebate_IOU = ['PG&E','SCE','SoCalGas','SDG&E']
        if self.iou in rebate_IOU:
            for battery in battery_cost_dict:
                battery_cost_dict[battery] = 0.75*battery_cost_dict[battery]
        
        if self.low_income_housing == 'yes':
             for battery in battery_cost_dict:
                battery_cost_dict[battery] = 0.15*battery_cost_dict[battery]
        return battery_cost_dict

        
    def get_generation_profile(self):
        solar_panel_specs = {'array_type': self.array_type,\
                         'azimuth': self.azimuth,\
                         'tilt': self.tilt,\
                         'system_capacity': self.system_capacity,\
                         'dc_ac_ratio': self.dc_ac_ratio,\
                         'module_type':self.module_type}
        solar_file = get_solar_profile(self.address,solar_panel_specs)
        return solar_file
        
    def process_solar_data(self,solar_file):
        solar_df = pd.read_csv(solar_file,header=0)
        #solar_df = solar_df.rename(columns= {',':'Hour'})
        solar_df['Hour'] = range(len(solar_df))
        solar_df['Generation'] =  solar_df['Generation']/1000
        solar_df = solar_df[['Hour','Generation']]
        solar_df = solar_df[solar_df['Hour'] <=8759]
        solar_df.to_csv(os.path.join(os.getcwd(),'solar_output.csv'),header=True)



    def get_load_profile(self):
        idf_path = self.building_file
        weather_path = self.weather_file
        load_file = run_energyplus_simulation(idf_path, weather_path)
        return load_file

    def process_load_data(self,load_file):
        load_df = pd.read_csv(load_file,header=0)
        load_df['Hour'] = range(len(load_df))
        load_df['Load'] = load_df['Electricity:Facility [J](Hourly)'] / 3600000
        load_df = load_df[['Hour','Load']]
        load_df = load_df[load_df['Hour'] <= 8759]
        load_df.to_csv(os.path.join(os.getcwd(),'load_output.csv'),header=True)

    

    
    def updated_hourly_profiles(self,plan,load_file):
        solar_df = pd.read_csv('solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        solar_df['Hour'] = solar_df['Hour'].apply(convert_utc_to_pt)
        load_df = pd.read_csv(load_file)
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        load_df.to_csv(os.path.join(os.getcwd(), 'original_hourly_load.csv'))
        merged_df = solar_df.merge(load_df, on = ['Day','Hour'])
        merged_df['Season'] = np.where((merged_df['Day'] >= 151) & (merged_df['Day'] <= 272), 'summer', 'winter')
        merged_df['day_of_week'] = (merged_df['Day'] % 7)
        merged_df['Weekend'] = merged_df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)
        if plan =='NEM' and '4' in self.tariff:
            merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        if plan =='NEM' and '5' in self.tariff:
            merged_df['Pricing'] = np.where((merged_df['Hour'] >= 17) & (merged_df['Hour'] <= 19) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 17) & (merged_df['Hour'] <= 19) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        if plan == 'NBT' and 'EV' not in self.tariff:
            merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        if 'EV' in self.tariff:
             merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20),
            'peak',
            np.where((merged_df['Hour'] >= 0) & (merged_df['Hour'] <= 6),
            'super_off_peak',
            'off_peak'
            )
            )
            
        merged_df['Month'] = merged_df.apply(get_month,axis=1)
        merged_df = merged_df[['Hour', 'Day','Weekend', 'Season', 'Load','Generation','Pricing','Month']]
        merged_df = merged_df.rename(columns = {'Load':'hourly_load', 'Generation':'hourly_generation'})
        solar_df = pd.read_csv('solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        solar_df['Hour'] = solar_df['Hour'].apply(convert_utc_to_pt)
        load_df = pd.read_csv(load_file)
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        comb_df = solar_df.merge(load_df, on = ['Day','Hour'])
        comb_df = comb_df[['Hour', 'Day', 'Load','Generation']]
        comb_df['Gen_Hour'] = np.where(comb_df['Generation'] > 0, 1, 0)
        gen_df = comb_df[comb_df['Hour'] <=15]
        gen_df = gen_df.groupby('Day')[['Generation','Gen_Hour']].sum().reset_index()
        daily_load = comb_df.groupby('Day')['Load'].sum().reset_index()
        daily_load = daily_load.rename(columns={'Load': 'daily_load'})
        if plan == 'NEM' and '5' in self.tariff:
            load_df = comb_df[(comb_df['Hour'] >= 17) & (comb_df['Hour'] <= 19)]
        if plan == 'NEM' and '4' in self.tariff:
            load_df = comb_df[(comb_df['Hour'] >= 16) & (comb_df['Hour'] <= 20)]
        if plan == 'NBT':
            load_df = comb_df[(comb_df['Hour'] >= 16) & (comb_df['Hour'] <= 20)]
        load_df = load_df.groupby('Day')['Load'].sum().reset_index()
        final_df = gen_df.merge(load_df, on = 'Day')
        final_df = final_df.merge(daily_load, on='Day')
        final_df = final_df.rename(columns = {'Load':'peak_load', 'Generation':'solar_generation'})
        battery_df = final_df.merge(merged_df, on='Day')
        sorted_df = battery_df.sort_values(by=['Day','Hour'])
        return sorted_df

    
    def hourly_profiles(self,plan,load_file):
        solar_df = pd.read_csv('solar_output.csv')
        solar_df['Day'] = solar_df['Hour'] // 24
        solar_df['Hour'] = solar_df['Hour']%24
        solar_df['Hour'] = solar_df['Hour'].apply(convert_utc_to_pt)
        load_df = pd.read_csv(load_file)
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        merged_df = solar_df.merge(load_df, on = ['Day','Hour'])
        merged_df['Season'] = np.where((merged_df['Day'] >= 151) & (merged_df['Day'] <= 272), 'summer', 'winter')
        merged_df['day_of_week'] = (merged_df['Day'] % 7)
        merged_df['Weekend'] = merged_df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)
        if plan =='NEM' and '4' in self.tariff:
            merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        
        if plan =='NEM' and '5' in self.tariff:
            merged_df['Pricing'] = np.where((merged_df['Hour'] >= 17) & (merged_df['Hour'] <= 19) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 17) & (merged_df['Hour'] <= 19) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )

        if plan == 'NBT':
            merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 0),
            'peak',
            np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20) & (merged_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )

        if 'EV' in self.tariff:
             merged_df['Pricing'] = np.where((merged_df['Hour'] >= 16) & (merged_df['Hour'] <= 20),
            'peak',
            np.where((merged_df['Hour'] >= 0) & (merged_df['Hour'] <= 6),
            'super_off_peak',
            'off_peak'
            )
            )
             
        merged_df['Month'] = merged_df.apply(get_month,axis=1)
        merged_df = merged_df[['Hour', 'Day','Weekend', 'Season', 'Load','Generation','Pricing','Month']]
        merged_df = merged_df.rename(columns = {'Load':'hourly_load', 'Generation':'hourly_generation'})
        return merged_df
    

    def get_load_dict(self,plan,load_file):
        load_dict = {x:{} for x in range(1,13)}
        if 'EV' not in self.tariff:
            tiers = ['summer_peak','summer_off_peak', 'summer_mid_peak', 'winter_peak','winter_off_peak','winter_mid_peak']
        if 'EV' in self.tariff:
            tiers = ['summer_peak','summer_off_peak', 'summer_super_off_peak', 'winter_peak','winter_off_peak','winter_super_off_peak']
        for key in load_dict:
            load_dict[key] = {x:0 for x in tiers}
        
        load_df = pd.read_csv(load_file)
        load_df['Day'] = load_df['Hour'] // 24
        load_df['Hour'] = load_df['Hour']%24
        load_df['Month'] = load_df.apply(get_month,axis=1)
        load_df['day_of_week'] = (load_df['Day'] % 7)
        load_df['Weekend'] = load_df['day_of_week'].apply(lambda x: 1 if x in [5, 6] else 0)
        if plan == 'NEM' and '4' in self.tariff:
            load_df['Pricing'] = np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 20) & (load_df['Weekend'] == 0),
            'peak',
            np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 20) & (load_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        
        if plan == 'NEM' and '5' in self.tariff:
            load_df['Pricing'] = np.where((load_df['Hour'] >= 17) & (load_df['Hour'] <= 19) & (load_df['Weekend'] == 0),
            'peak',
            np.where((load_df['Hour'] >= 17) & (load_df['Hour'] <= 19) & (load_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )

        if plan == 'NBT':
            load_df['Pricing'] = np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 20) & (load_df['Weekend'] == 0),
            'peak',
            np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 20) & (load_df['Weekend'] == 1),
            'mid_peak',
            'off_peak'
            )
            )
        
        if 'EV' in self.tariff:
            load_df['Pricing'] = np.where((load_df['Hour'] >= 16) & (load_df['Hour'] <= 20),
            'peak',
            np.where((load_df['Hour'] >= 0) & (load_df['Hour'] <= 6),
            'super_off_peak',
            'off_peak'
            )
            )
        
        load_df['Season'] = np.where((load_df['Day'] >= 151) & (load_df['Day'] <= 272), 'summer', 'winter')
        load_df = load_df.groupby(['Month','Season','Pricing'])['Load'].sum().reset_index()
        for i in range(len(load_df)):
            month = load_df.loc[i,'Month']
            pricing = load_df.loc[i,'Pricing']
            season = load_df.loc[i,'Season']
            load = load_df.loc[i,'Load']
            load_dict[month][f'{season}_{pricing}'] = load 
        return load_dict
    
    
    def get_export_dict(self):
        export_dict = {x:{} for x in range(1,13)}
        if 'EV' not in self.tariff:
            tiers = ['summer_peak','summer_off_peak', 'summer_mid_peak', 'winter_peak','winter_off_peak','winter_mid_peak']
        if 'EV' in self.tariff:
            tiers = ['summer_peak','summer_off_peak', 'summer_super_off_peak', 'winter_peak','winter_off_peak','winter_super_off_peak']
        for key in export_dict:
            export_dict[key] = {x:0 for x in tiers}
        return export_dict


    def get_delivery_profile(self,load_dict):
        df = pd.DataFrame.from_dict(load_dict, orient='index')
        df['Month'] = df.index
        df_pivot = df.melt(id_vars='Month', var_name='tou_period', value_name='kwh')
        return df_pivot

    def get_export_profile(self,export_dict):
        df = pd.DataFrame.from_dict(export_dict, orient='index')
        df['Month'] = df.index
        df_pivot = df.melt(id_vars='Month', var_name='tou_period', value_name='kwh')
        return df_pivot
    
    def get_break_even_time(self, cost_dict, savings_dict):
        break_even_dict = {}
        for battery in cost_dict:
            break_even_dict[battery] = round(int(cost_dict[battery])/int(savings_dict[battery]),1)
        return break_even_dict
        

        
    def plot_battery_savings(self, savings):
        battery_types = list(savings.keys())
        values = list(savings.values())
        plt.figure(figsize=(10, 6))
        bars = plt.bar(battery_types, values, color='skyblue')
        plt.xlabel('Battery Types')
        plt.ylabel('Savings')
        plt.title('Battery Types vs Savings')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        for bar, value in zip(bars, values):
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval, round(value, 2), ha='center', va='bottom', fontsize=9)
        plot_filename = 'battery_plot.png'
        plt.savefig(os.path.join('static/images', plot_filename))
        plt.close()

    def plot_break_even_time(self,break_even_dict):
        battery_types = list(break_even_dict.keys())
        values = list(break_even_dict.values())
        sorted_values = sorted(values)
        lowest_two_values = set(sorted_values[:2])
        colors = ['green' if value in lowest_two_values else 'grey' for value in values]
        plt.figure(figsize=(10, 6))
        bars = plt.bar(battery_types, values, color=colors)
        plt.xlabel('Battery Types')
        plt.ylabel('Break Even Time (Years)')
        plt.title('Battery Types vs Break Even Time')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        for bar, value in zip(bars, values):
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval, round(value, 2), ha='center', va='bottom', fontsize=9)
        plot_filename = 'break_even_plot.png'
        plt.savefig(os.path.join('static/images', plot_filename))
        plt.close()

    
    def plot_solar_load(self):
        df = pd.read_csv('solar_load.csv')
        df_non_zero = df[df['kwh'] != 0]
        df_pivot = df_non_zero.pivot_table(index='Month', columns='tou_period', values='kwh')
        plt.figure(figsize=(12, 8))
        for column in df_pivot.columns:
            plt.plot(df_pivot.index, df_pivot[column], marker='o', label=column)

        plt.xlabel('Month')
        plt.ylabel('Load')
        plt.title('Load Values by Month and TOU Period')
        plt.legend(title='TOU Period')
        plt.grid(True)
        plt.xticks(df_pivot.index)
        plt.tight_layout()
        plot_filename = 'solar_load_plot.png'
        plt.savefig(os.path.join('static/images', plot_filename))
        plt.close()

    def plot_hourly_profiles(self):
        df = pd.read_csv('final_hourly_load.csv')
        df_daily = df[df['Day'] == 0]
        plt.figure(figsize=(10, 6))  # Optional: Adjust the size of the plot
        plt.plot(df_daily['Hour'], df_daily['Load'], label='Load', color='blue', marker='o')
        plt.plot(df_daily['Hour'], df_daily['Paired_Load'], label='Paired Load', color='red', marker='x')
        plt.xlabel('Hour')
        plt.ylabel('Value')
        plt.title('Load Shift with Addition of Paired System')
        plt.legend()
        plt.grid(True)
        plot_filename = 'daily_profile_plot.png'
        plt.savefig(os.path.join('static/images', plot_filename))
        plt.close()








    



        






        





        


        
        
        


    

            





       

