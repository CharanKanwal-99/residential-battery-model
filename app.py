from flask import Flask, render_template,request, send_file
from main import ProcessCustomerDetails
from grid_impact import GridImpact
import os


app = Flask(__name__)


@app.route('/home',methods = ['GET'])
def customer_data():
    return render_template('home1.html')
    
    
@app.route('/grid',methods=['GET'])
def grid_impact():
    return render_template('grid.html')


@app.route('/savings',methods=['GET'])
def savings():
    return render_template('home2.html')




    


@app.route('/prediction',methods = ['POST'])
def prediction():
    if request.method == 'POST':
        address = request.form.get('address')
        iou = request.form.get('iou')
        low_income_housing = request.form.get('low_income_housing')
        battery_type = request.form.get('battery_type')
        solar_data = request.form.get('solar_data')
        interconnection_date = request.form.get('interconnection_date')
        solar_pairing = request.form.get('solar_pairing')
        array_type = request.form.get('array_type')
        azimuth = request.form.get('azimuth')
        tilt = request.form.get('tilt')
        system_capacity = request.form.get('system_capacity')
        dc_ac_ratio = request.form.get('dc_ac_ratio')
        module_type = request.form.get('module_type')
        location = request.form.get('location')
        climate = request.form.get('climate_zone')
        tariff = request.form.get('tariff_plan')
        file = request.files['csv_file']
        if file.filename != '':
            file_path = os.path.join(os.getcwd(), 'customer_load.csv')
            file.save(file_path)
        load_file = file.filename
        customer = ProcessCustomerDetails(address,iou,low_income_housing,battery_type,solar_data,interconnection_date,solar_pairing,array_type,azimuth,tilt,system_capacity,dc_ac_ratio,module_type,location,climate,tariff,load_file)
        values = customer.run()
        saving = values[0]
        battery_bill = values[1]
        solar_bill = values[2]
        years = values[3]
        
    return render_template('prediction.html',savings=saving, battery_bill=battery_bill, solar_bill=solar_bill,years=years)


@app.route('/prediction1',methods = ['POST'])
def prediction_grid():
    if request.method == 'POST':
        #load_file = request.files['loadProfile']
        load_file = ''
        batteries = request.form.get('numBatteries')
        county = request.form.get('county')
        composition = {}
        composition['Tesla Powerwall - 13.5kWh'] = request.form.get('battery_1')
        composition['Ecoflow DPU + Smart Home Panel-6kwh'] = request.form.get('battery_2')
        composition['Anker Solix X1-3kwh'] = request.form.get('battery_3')
        composition['Generac PWRcell-9kwh'] = request.form.get('battery_4')
        composition['Enphase IQ Battery 10T-10kwh'] = request.form.get('battery_5')
        grid_impact = GridImpact(load_file,batteries, composition, county)
        table_html = grid_impact.run()
    return render_template('prediction1.html', table_html=table_html,batteries=batteries)


@app.route('/monthly', methods=['GET'])
def monthly_file():
    csv_file_path = 'grid_impact_monthly.csv'
    return send_file(
        csv_file_path,
        mimetype='text/csv',
        as_attachment=True
    )

@app.route('/battery', methods=['GET'])
def battery_file():
    csv_file_path = 'grid_impact_battery.csv'
    return send_file(
        csv_file_path,
        mimetype='text/csv',
        as_attachment=True
    )



if __name__ == '__main__':
    app.run(debug=False)

