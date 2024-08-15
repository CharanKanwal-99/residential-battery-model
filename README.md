# residential-battery-savings
This project analyzes the savings associated with Residential Batteries in California under the different tariff plans of different utilities. Since there is significant solar penetration in California, there is an option to calculate savings with and without solar pairing. Two major aspects of the analysis are the load and generation profiles. Pvwatts has been used for getting the user's solar generation profiles while the DOE's EnergyPlus model is used to get load profiles based on building and weather data. A flask app has been created for the calculation of savings.

Running Locally:
Install Energyplus version 9.5 on your system since that specific version is the one which works with the residential building files used for the simulation
Keep the IDD file which is part of the installation in the relevant directory as mentioned in the code in load_profile

You can download Residential Building Files from: https://www.energycodes.gov/prototype-building-models#Residential. Download the relevant climate zones files.
You can download weather files in epw format from the Energyplus website itself: https://energyplus.net/weather
These weather files have been stored under the weather files directory in the code. You can download all files and store them there


