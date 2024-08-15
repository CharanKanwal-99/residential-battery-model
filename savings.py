import numpy as np
import pandas as pd
import os
import copy
from utils import get_days



class Billing():
  def __init__(self,delivery_profile, export_profile, pricing_dict,plan):
    self.delivery_profile = delivery_profile
    self.export_profile = export_profile
    self.pricing_dict = pricing_dict
    self.plan = plan

  def tou_rate(self,df):
    if df['kwh'] >= 0:
      tou_period = df['tou_period'] + '_price'
      return self.pricing_dict['tou_d'][tou_period]
    else:
      tou_period = df['tou_period'] + '_export'
      if self.plan == 'NEM':
        return self.pricing_dict['tou_d'][tou_period]
      if self.plan == 'NBT':
         return self.pricing_dict['tou_d'][tou_period][df['Month']]


  def non_bypassable(self,df):
    return self.pricing_dict['NBC']

  def basic_charges(self,df):
    return self.pricing_dict['Basic_Charge']*df['Days']

  def min_charges(self,df):
    return self.pricing_dict['Min_Charge']*df['Days']


  def baseline_credit(self,df):
    if 6<=df['Month']<=9:
      if abs(df['kwh']) <= 12.8*df['Days']:
        return self.pricing_dict['Baseline']*df['kwh']
      if abs(df['kwh']) > 12.8*df['Days']:
        if df['kwh'] > 0:
          return 12.8*df['Days']*self.pricing_dict['Baseline']
        else:
          return -12.8*df['Days']*self.pricing_dict['Baseline']


    if df['Month'] > 9 or df['Month'] < 6:
      if abs(df['kwh']) <= 10.3*df['Days']:
        return self.pricing_dict['Baseline']*df['kwh']
      if abs(df['kwh']) > 10.3*df['Days']:
        if df['kwh'] > 0:
          return 10.3*df['Days']*self.pricing_dict['Baseline']
        else:
          return -10.3*df['Days']*self.pricing_dict['Baseline']



  def get_billing(self):
    self.delivery_profile['price'] = self.delivery_profile.apply(self.tou_rate,axis=1)
    self.delivery_profile['charges'] = self.delivery_profile['price']*self.delivery_profile['kwh']
    self.delivery_profile = self.delivery_profile.groupby('Month')[['kwh','charges']].sum().reset_index()
    self.delivery_profile = self.delivery_profile.rename(columns = {'kwh':'kwh_d','charges':'charges_d'})

    self.export_profile['price'] = self.export_profile.apply(self.tou_rate,axis=1)
    self.export_profile['charges'] = self.export_profile['price']*self.export_profile['kwh']
    self.export_profile = self.export_profile.groupby('Month')[['kwh','charges']].sum().reset_index()
    self.export_profile = self.export_profile.rename(columns = {'kwh':'kwh_r','charges':'charges_r'})
    merged_profile = self.delivery_profile.merge(self.export_profile, on = 'Month')
    merged_profile['Days'] = merged_profile.apply(get_days,axis=1)
    merged_profile['charges'] = merged_profile['charges_d'] + merged_profile['charges_r']
    merged_profile['kwh'] = merged_profile['kwh_d'] + merged_profile['kwh_r']
    merged_profile['Baseline_Credit'] = merged_profile.apply(self.baseline_credit,axis=1)
    merged_profile['NBC'] = merged_profile.apply(self.non_bypassable,axis=1)
    merged_profile['NBC'] = merged_profile['NBC']*merged_profile['kwh_d']
    merged_profile['Basic_Charges'] = merged_profile.apply(self.basic_charges,axis=1)
    merged_profile['Min_Charges'] = merged_profile.apply(self.min_charges,axis=1)
    merged_profile['Min Charges/NBC'] = np.maximum(merged_profile['NBC'] + merged_profile['Basic_Charges'], merged_profile['Min_Charges'])
    merged_profile['Other Items'] = merged_profile['charges']+ merged_profile['Baseline_Credit']
    other_items = np.maximum(merged_profile['Other Items'].sum(), 0)
    min_charge = merged_profile['Min Charges/NBC'].sum()
    net_surplus = merged_profile['kwh_d'].sum() + merged_profile['kwh_r'].sum()
    net_comp = (net_surplus < 0)*0.02758*abs(net_surplus)
    annual_bill = other_items+ min_charge - net_comp
    return int(annual_bill)






   
def get_updated_battery_savings(df,load_dict,export_dict, eff_capacity, plan):
  load_dict1 = copy.deepcopy(load_dict)
  export_dict1 = copy.deepcopy(export_dict)
  load_change = {x:0 for x in range(365)}
  for key in load_change:
    load_change[key] = {x:0 for x in range(24)}
  if plan == 'NEM':
    batt_charged = {x:0 for x in range(365)}
  
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
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour] -= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour] -= hourly_load
            if batt_charged[day] > eff_capacity:
              excess = batt_charged[day]-eff_capacity
              batt_charged[day]-=excess
              if hourly_generation >= max_hourly_charge:
                hourly_generation -= max_hourly_charge
                hourly_generation+= excess
              if hourly_generation < max_hourly_charge:
                hourly_generation = excess
              if hourly_generation < hourly_load:
                load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                load_change[day][hour] -= hourly_generation
              if hourly_generation > hourly_load:
                load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                load_change[day][hour] -= hourly_load
              continue
          if batt_charged[day] == eff_capacity:
            if hourly_generation < hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
              load_change[day][hour] -= hourly_generation
            if hourly_generation > hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_load
              export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
              load_change[day][hour] -= hourly_load


        
        if pricing =='peak' or pricing == 'mid_peak':
          if hourly_generation <= hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
            eff_hourly_load = hourly_load-hourly_generation
            load_change[day][hour] -= hourly_generation
          if hourly_generation > hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_load
            export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            eff_hourly_load=0
            load_change[day][hour] -= hourly_load
          
          if batt_charged[day] > 0:
            if batt_charged[day] >= eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
              batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
              load_change[day][hour] -= min(max_hourly_discharge, eff_hourly_load)
            if batt_charged[day] < eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
              batt_charged[day]=0
              load_change[day][hour] -= batt_charged[day]
          
          if hour==19 and batt_charged[day] > 0:
            export_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
            batt_charged[day]=0
            


        
      


        
      if solar_generation < eff_capacity:
        if pricing == 'off_peak':
          if batt_charged[day] < solar_generation:
            batt_charged[day] += min(hourly_generation, max_hourly_charge)
            if batt_charged[day] < solar_generation:
              if hourly_generation > max_hourly_charge:
                hourly_generation -= max_hourly_charge
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour] -= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour] -= hourly_load
            if batt_charged[day] > solar_generation:
              excess = batt_charged[day]-solar_generation
              batt_charged[day]-=excess
              if hourly_generation >= max_hourly_charge:
                hourly_generation -= max_hourly_charge
                hourly_generation+= excess
              if hourly_generation < max_hourly_charge:
                hourly_generation = excess
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour] -= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour] -= hourly_load
              continue
          if batt_charged[day] == solar_generation:
            if hourly_generation < hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
              load_change[day][hour] -= hourly_generation
            if hourly_generation > hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_load
              export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
              load_change[day][hour] -= hourly_load
          
          if hour == 10:
            load_dict1[month][f'{season}_{pricing}'] += eff_capacity-solar_generation
            batt_charged[day] += eff_capacity-solar_generation
            load_change[day][hour] += eff_capacity-solar_generation

        
        if pricing =='peak' or pricing == 'mid_peak':
          if hourly_generation <= hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
            eff_hourly_load = hourly_load-hourly_generation
            load_change[day][hour] -= hourly_generation
          if hourly_generation > hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_load
            export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            eff_hourly_load = 0
            load_change[day][hour] -= hourly_load
          if batt_charged[day] > 0:
            if batt_charged[day] >= eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
              batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
              load_change[day][hour] -= min(max_hourly_discharge, eff_hourly_load)
            if batt_charged[day] < eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
              batt_charged[day]=0
              load_change[day][hour] -= batt_charged[day]
          if hour==19 and batt_charged[day] > 0:
            export_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
            batt_charged[day]=0
            
          
          

      
            

  if plan == 'NBT':
    batt_charged = {x:0 for x in range(365)}

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
      if peak_load <= eff_capacity and solar_generation >= peak_load:
        if pricing == 'off_peak':
          if batt_charged[day] < peak_load:
            batt_charged[day] += min(hourly_generation, max_hourly_charge)
            if batt_charged[day] < peak_load:
              if hourly_generation > max_hourly_charge:
                hourly_generation -= max_hourly_charge
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  load_change[day][hour]-= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            if batt_charged[day] > peak_load:
              excess = batt_charged[day]-peak_load
              batt_charged[day]-=excess
              if hourly_generation >= max_hourly_charge:
                hourly_generation -= max_hourly_charge
                hourly_generation+= excess
              if hourly_generation < max_hourly_charge:
                hourly_generation = excess
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
              continue
          if batt_charged[day] == peak_load:
            if hourly_generation < hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
              load_change[day][hour]-= hourly_generation
            if hourly_generation > hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_load
              load_change[day][hour]-= hourly_load
              export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load


        
        if pricing =='peak' or pricing == 'mid_peak':
          if hour==16:
            batt_charged[day] = 0.9*batt_charged[day]
          if hourly_generation < hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
            eff_hourly_load = hourly_load-hourly_generation
            load_change[day][hour]-= hourly_generation
          if hourly_generation > hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_load
            export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            load_change[day][hour]-= hourly_load
            eff_hourly_load=0
          if batt_charged[day] > 0:
            if batt_charged[day] >= eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
              batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
              load_change[day][hour]-= eff_hourly_load
            if batt_charged[day] < eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
              load_change[day][hour]-= batt_charged[day]
              batt_charged[day]=0
          if hour==20 and batt_charged[day] > 0:
            export_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
            batt_charged[day]=0



        
      if solar_generation < peak_load and eff_capacity>=peak_load:

        if pricing == 'off_peak':
          if batt_charged[day] < solar_generation:
            batt_charged[day] += min(hourly_generation, max_hourly_charge)
            if batt_charged[day] < solar_generation:
              if hourly_generation > max_hourly_charge:
                hourly_generation -= max_hourly_charge
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
            if batt_charged[day] > solar_generation:
              excess = batt_charged[day]-solar_generation
              batt_charged[day]-=excess
              if hourly_generation >= max_hourly_charge:
                hourly_generation -= max_hourly_charge
                hourly_generation+= excess
              if hourly_generation < max_hourly_charge:
                hourly_generation = excess
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
              continue
          if batt_charged[day] == solar_generation:
            if hourly_generation < hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
              load_change[day][hour]-= hourly_generation
            if hourly_generation > hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_load
              export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
              load_change[day][hour]-= hourly_load
          
          if hour == 10:
            load_dict1[month][f'{season}_{pricing}'] += peak_load-solar_generation
            batt_charged[day] += peak_load-solar_generation
            load_change[day][hour] += peak_load-solar_generation

        
        if pricing =='peak' or pricing == 'mid_peak':
          if hour==16:
            batt_charged[day] = 0.9*batt_charged[day]
          if hourly_generation < hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
            load_change[day][hour]-= hourly_generation
            eff_hourly_load = hourly_load-hourly_generation
          if hourly_generation > hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_load
            export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            load_change[day][hour]-= hourly_load
            eff_hourly_load=0
          if batt_charged[day] > 0:
            if batt_charged[day] >= eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
              batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
              load_change[day][hour]-= min(max_hourly_discharge, eff_hourly_load)
            if batt_charged[day] < eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
              load_change[day][hour]-= batt_charged[day]
              batt_charged[day]=0
          if hour==20 and batt_charged[day] > 0:
            export_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
            batt_charged[day]=0

      if eff_capacity < peak_load and solar_generation > eff_capacity:
        if pricing == 'off_peak':
          if batt_charged[day] < eff_capacity:
            batt_charged[day] += min(hourly_generation, max_hourly_charge)
            if batt_charged[day] < eff_capacity:
              if hourly_generation > max_hourly_charge:
                hourly_generation -= max_hourly_charge
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
            if batt_charged[day] > eff_capacity:
              excess = batt_charged[day]-eff_capacity
              batt_charged[day]-=excess
              if hourly_generation >= max_hourly_charge:
                hourly_generation -= max_hourly_charge
                hourly_generation+= excess
              if hourly_generation < max_hourly_charge:
                hourly_generation = excess
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
              continue
          if batt_charged[day] == eff_capacity:
            if hourly_generation < hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
              load_change[day][hour]-= hourly_generation
            if hourly_generation > hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_load
              export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
              load_change[day][hour]-= hourly_load

      


        
        if pricing =='peak' or pricing == 'mid_peak':
          if hour==16:
            batt_charged[day] = 0.9*batt_charged[day]
          if hourly_generation < hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
            eff_hourly_load = hourly_load-hourly_generation
            load_change[day][hour]-= hourly_generation
          if hourly_generation > hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_load
            export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            load_change[day][hour]-= hourly_load
            eff_hourly_load=0
          if batt_charged[day] > 0:
            if batt_charged[day] >= eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
              batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
              load_change[day][hour]-= min(max_hourly_discharge, eff_hourly_load)
            if batt_charged[day] < eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
              batt_charged[day]=0
              load_change[day][hour]-= batt_charged[day]
          if hour==20 and batt_charged[day] > 0:
            export_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
            batt_charged[day]=0


        
      if eff_capacity < peak_load and solar_generation < eff_capacity:
        
        if pricing == 'off_peak':
          if batt_charged[day] < solar_generation:
            batt_charged[day] += min(hourly_generation, max_hourly_charge)
            if batt_charged[day] < solar_generation:
              if hourly_generation > max_hourly_charge:
                hourly_generation -= max_hourly_charge
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
            if batt_charged[day] > solar_generation:
              excess = batt_charged[day]-solar_generation
              batt_charged[day]-=excess
              if hourly_generation >= max_hourly_charge:
                hourly_generation -= max_hourly_charge
                hourly_generation+= excess
              if hourly_generation < max_hourly_charge:
                hourly_generation = excess
                if hourly_generation < hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
                  load_change[day][hour]-= hourly_generation
                if hourly_generation > hourly_load:
                  load_dict1[month][f'{season}_{pricing}'] -= hourly_load
                  export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
                  load_change[day][hour]-= hourly_load
              continue
          if batt_charged[day] == solar_generation:
            if hourly_generation < hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
              load_change[day][hour]-= hourly_generation
            if hourly_generation > hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= hourly_load
              export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
              load_change[day][hour]-= hourly_load
          
          if hour == 10:
            load_dict1[month][f'{season}_{pricing}'] += eff_capacity-solar_generation
            batt_charged[day] += eff_capacity-solar_generation
            load_change[day][hour] += eff_capacity-solar_generation

        
        if pricing =='peak' or pricing == 'mid_peak':
          if hour==16:
            batt_charged[day] = 0.9*batt_charged[day]
          if hourly_generation < hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_generation
            eff_hourly_load = hourly_load-hourly_generation
            load_change[day][hour]-= hourly_generation
          if hourly_generation > hourly_load:
            load_dict1[month][f'{season}_{pricing}'] -= hourly_load
            export_dict1[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
            load_change[day][hour]-= hourly_load
            eff_hourly_load=0
          if batt_charged[day] > 0:
            if batt_charged[day] >= eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= min(max_hourly_discharge, eff_hourly_load)
              batt_charged[day]-= min(max_hourly_discharge, eff_hourly_load)
              load_change[day][hour]-= min(max_hourly_discharge, eff_hourly_load)
            if batt_charged[day] < eff_hourly_load:
              load_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
              load_change[day][hour]-= batt_charged[day]
              batt_charged[day]=0
          if hour==20 and batt_charged[day] > 0:
            export_dict1[month][f'{season}_{pricing}'] -= batt_charged[day]
            batt_charged[day]=0

  return load_dict1, export_dict1,load_change
      



   
    


def get_solar_savings(df,load_dict,export_dict):
  load_dict2 = copy.deepcopy(load_dict)
  export_dict2 = copy.deepcopy(export_dict)
  load_change = {x:0 for x in range(365)}
  for key in load_change:
    load_change[key] = {x:0 for x in range(24)}
  for i in range(len(df)):
    hourly_generation = df.loc[i,'hourly_generation']
    hourly_load = df.loc[i,'hourly_load']
    season = df.loc[i,'Season']
    pricing = df.loc[i,'Pricing']
    month = df.loc[i,'Month']
    weekend = df.loc[i,'Weekend']
    day = df.loc[i,'Day']
    hour = df.loc[i,'Hour']
    if hourly_generation < hourly_load:
      load_dict2[month][f'{season}_{pricing}'] -= hourly_generation
      load_change[day][hour] -= hourly_generation
    if hourly_generation > hourly_load:
      load_dict2[month][f'{season}_{pricing}'] -= hourly_load
      export_dict2[month][f'{season}_{pricing}'] -= hourly_generation-hourly_load
      load_change[day][hour] -= hourly_load
  return load_dict2,export_dict2, load_change
  
  

            
    



        

    




