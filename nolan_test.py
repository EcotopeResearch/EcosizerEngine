from ecoengine import getWeatherStations, EcosizerEngine, getListOfModels, SimulationRun, getAnnualSimLSComparison, PrefMapTracker
import time
import math
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter
import os

# pm = PrefMapTracker(None, 'MODELS_ColmacCxA_20_C_SP', numHeatPumps=1, usePkl=True, prefMapOnly = True)
# print("MODELS_ColmacCxA_20_C_SP secondaryHeatExchanger", pm.secondaryHeatExchanger)

# print(pm.default_input_low)
# print(pm.default_output_low)
# for i in range(10):
#     print(f"pm.getCapacity({25},{63+i},{140}) {pm.getCapacity(25,63+i,140)}")

# print(f"pm.getCapacity({25},{40},{148}) {pm.getCapacity(25,40,148)}")
# print(f"pm.getCapacity({25},{83},{134}) {pm.getCapacity(25,83,134)}")

# print("=============================================================")

# pm = PrefMapTracker(None, 'MODELS_Mitsubishi_QAHV_C_SP', numHeatPumps=1, usePkl=True, prefMapOnly = True)
# print("MODELS_Mitsubishi_QAHV_C_SP secondaryHeatExchanger", pm.secondaryHeatExchanger)

# print(f"pm.getCapacity({105.8},{89.51},{160-10}) {pm.getCapacity(105.8,89.51,160-10)}")
# # print(f"pm.getCapacity({-13-10},{67-10},{160}) {pm.getCapacity(-13-10,67-10,160)}")

# print("=============================================================")

# pm = PrefMapTracker(None, 'MODELS_LYNC_AEGIS_500_C_SP', numHeatPumps=1, usePkl=True, prefMapOnly = True)
# print("MODELS_LYNC_AEGIS_500_C_SP secondaryHeatExchanger", pm.secondaryHeatExchanger)

# print(f"pm.getCapacity({34},{74-10},{160-10}) {pm.getCapacity(34,74-10,160-10)}")
# print(f"pm.getCapacity({34-10},{74-10},{160}) {pm.getCapacity(34-10,74-10,160)}")

print(getWeatherStations())

# def createERSizingCurvePlot(x, y, startind, x_axis_label, x_units):
#     """
#     Sub - Function to plot the the x and y curve and create a point (secretly creates all the points)
#     """
#     fig = Figure()
    
#     hovertext = x_axis_label + ': %{x:.1f} ' + x_units + ' \nER Heating Capacity Increase: %{y:.1f}'

#     fig.add_trace(Scatter(x=x, y=y,
#                     visible=True,
#                     line=dict(color="#28a745", width=4),
#                     hovertemplate=hovertext,
#                     opacity=0.8,
#                     ))

#     # Add traces for the point, one for each slider step
#     for ii in range(len(x)):
#         fig.add_trace(Scatter(x=[x[ii]], y=[y[ii]], 
#                         visible=False,
#                         mode='markers', marker_symbol="diamond", 
#                         opacity=1, marker_color="#2EA3F2", marker_size=10,
#                         name="System Size",
#                         hoverlabel = dict(font=dict(color='white'), bordercolor="white")
#                         ))

#     # Make the 16 hour trace visible
#     # fig.data[startind+1].visible = True
#     fig.update_layout(title="Additional Electric Resistance Sizing Curve",
#                     xaxis_title=x_axis_label,
#                     yaxis_title="ER Heating Capacity Increase (kW)",
#                     showlegend=False)

#     return fig

W_TO_BTUHR = 3.412142

# hpwh = EcosizerEngine(
#             magnitudeStat  = 100,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             loadUpT_F       = 165,
#             percentUseable  = 0.9, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = 0.21,
#             aquaFractShed   = 0.8,
#             schematic       = 'swingtank_er', 
#             buildingType   = 'multi_family',
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 100, 
#             Wapt            = 60,
#             loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
#             loadUpHours     = 3,
#             doLoadShift     = False,
#             systemModel="MODELS_Mitsubishi_QAHV_C_SP",
#             PVol_G_atStorageT=1000,
#             numHeatPumps=2,
#             TMVol_G = 50,
#             TMCap_kW = 10,
#             annual = True,
#             sizeAdditionalER = False,
#             climateZone=32
#         )
hpwh = EcosizerEngine(
            magnitudeStat  = 100,
            supplyT_F       = 120,
            storageT_F      = 145,
            percentUseable  = 0.9, 
            aquaFract       = 0.4,
            schematic       = 'swingtank_er',
            buildingType   = 'multi_family',
            gpdpp           = 25,
            safetyTM        = 1.75,
            defrostFactor   = 1,
            nApt            = 100,
            Wapt            = 60,
            doLoadShift     = False,
            # systemModel="MODELS_SANCO2_C_SP",
            PCap_kW=5,
            PVol_G_atStorageT=150,
            numHeatPumps=1,
            TMVol_G = 119,
            TMCap_kW = 50,
            annual = True,
            sizeAdditionalER = True,
            climateZone= 70
        )
# hpwh2 = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 100,
#             supplyT_F       = 120,
#             storageT_F      = 145,
#             loadUpT_F       = 145,
#             percentUseable  = 0.9, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = 0.21,
#             aquaFractShed   = 0.8,
#             schematic       = 'swingtank', 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 100, 
#             Wapt            = 60,
#             loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
#             loadUpHours     = 3,
#             doLoadShift     = False,
#             loadShiftPercent       = 1.,
#             annual = False,
#             sizeAdditionalER = True,
#             zipCode=90210
#         )
print("hpwh.system.TMCap_kBTUhr / W_TO_BTUHR",hpwh.system.TMCap_kBTUhr / W_TO_BTUHR)
simRun = hpwh.getSimRun(minuteIntervals=15, nDays=365, exceptOnWaterShortage=False)
# simRun, utility_cost = hpwh.utilityCalculation(5.00, [16,23], [21,24], [38.75,38.75], [0.21585,0.5], [30.20,35.0], [0.14341,0.07],[0,5],[5,12]) #csv_path = os.path.join(os.path.dirname(__file__),'test.csv')
# simRun.writeCSV("13_gpdpp.csv")
# print(f"total utility cost is ${round(utility_cost,2)}")

# if True:
# # Generate the content for the HTML div
#     content = hpwh.erSizedPointsPlot()
#     # content = hpwh2.plotSizingCurve(returnAsDiv = True)
#     print(hpwh2.getSizingResults())
#     # Create the HTML content
#     html_content = f"""<!DOCTYPE html>
# <html>
# <head>
#     <title>My Webpage</title>
#     <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
# </head>
# <body>
# <div>
# {content}
# </div>
# </body>
# </html>
# """

#     # Write the HTML content to the file
#     file_name = f'er_result_graph_non_an_15.html'
#     with open(file_name, 'w') as file:
#         file.write(html_content)

# print(f"{hpwh.system.TMCap_kBTUhr} {hpwh.system.TMCap_kBTUhr / W_TO_BTUHR}")
# print("=================Annual=======================")
# hpwh = EcosizerEngine(
#         incomingT_F     = 50,
#         magnitudeStat  = 100,
#         supplyT_F       = 120,
#         storageT_F      = 145,
#         loadUpT_F       = 145,
#         percentUseable  = 0.9, 
#         aquaFract       = 0.4, 
#         aquaFractLoadUp = 0.21,
#         aquaFractShed   = 0.8,
#         schematic       = 'swingtank_er', 
#         buildingType   = 'multi_family',
#         returnT_F       = 0, 
#         flowRate       = 0,
#         gpdpp           = 25,
#         safetyTM        = 1.75,
#         defrostFactor   = 1, 
#         compRuntime_hr  = 16, 
#         nApt            = 100, 
#         Wapt            = 60,
#         loadShiftSchedule  = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,0,1],
#         loadUpHours     = 3,
#         doLoadShift     = False,
#         loadShiftPercent       = 1.,
#         PVol_G_atStorageT = 891, 
#         PCap_kW = 20,
#         TMVol_G = 100,
#         TMCap_kW = 19,
#         annual = True,
#         sizeAdditionalER = True
#     )
# print(f"{hpwh.system.TMCap_kBTUhr} {hpwh.system.TMCap_kBTUhr / W_TO_BTUHR}")
# hpwh.getSimRun(initPV=0.1, initST=135, minuteIntervals = 1, nDays = 365)
# for model in [["MODELS_Laars_eTherm_C_SP", 150]]:
#     print("=============================================================")
#     print(f"============{model}====================")
#     print("=============================================================")
#     for zip_code in [90506,92101,94115,95501]:
#         hpwh = EcosizerEngine(
#                     incomingT_F=0,
#                     magnitudeStat = 48,
#                     supplyT_F = 120,
#                     storageT_F = model[1],
#                     percentUseable = 0.95,
#                     aquaFract = 0.40,
#                     loadUpT_F = model[1],
#                     loadUpHours = 2,
#                     schematic = 'swingtank',
#                     buildingType  = 'multi_family',
#                     nApt = 19,
#                     Wapt = 60,
#                     doLoadShift   = False,
#                     climateZone=12,
#                     annual=True,
#                     gpdpp=25,
#                     systemModel=model[0],
#                     numHeatPumps=4,
#                     PVol_G_atStorageT=230,
#                     TMCap_kW=4,
#                     TMVol_G=40
#         )

#         simRun = hpwh.getSimRun(minuteIntervals = 15, nDays = 365)
#         print(f"{zip_code}: {simRun.building.getAvgIncomingWaterT()}")
#         print(f"number of times COP was forced for {hpwh.getClimateZone()}: {hpwh.system.perfMap.timesForcedCOP} and number assumed: {hpwh.system.perfMap.timesAssumedCOP} and number times storage temp should have been lowered: {hpwh.system.perfMap.timeStorageTempNeedToBeLowered}")
#         # simRun.writeCSV(f'SANCO2_{zip_code}_{hpwh.getClimateZone()}.csv')
#     print("=============================================================")

# hpwh = EcosizerEngine(
#             incomingT_F = 0,
#             magnitudeStat = 110,
#             supplyT_F = 120,
#             storageT_F = 150,
#             percentUseable = 0.95,
#             aquaFract = 0.4,
#             aquaFractLoadUp = 0.2,
#             aquaFractShed = 0.8,
#             loadUpT_F = 160,
#             loadUpHours = 2, # might need to change for future
#             schematic = "swingtank",
#             buildingType  = "multi_family",
#             gpdpp = 25,
#             nApt = 100,
#             Wapt = 60,
#             # standardGPD = 'ca',
#             # The 3 params below have to do with loadshift, the logic from here will have to be translated to get the right values https://github.com/EcotopeResearch/Ecosizer/blob/ee7cc4dee9014b40963c3a4323d878acb30b0501/HPWHulator/sizer/views.py#L309-L322
#             loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1],
#             doLoadShift   = True,
#             zipCode=91708, # CZ10
#             annual=True,
#             systemModel='MODELS_Mitsubishi_QAHV_C_SP',
#             PVol_G_atStorageT=1000,
#             # PCap_kW=262/W_TO_BTUHR,
#             numHeatPumps=1,
#             TMCap_kW=30,
#             TMVol_G=200,   
#         )

# outlist = hpwh.getSimRunWithkWCalc(minuteIntervals = 15, nDays = 365)
# simRun_ls = outlist[0]

# print(f"loadshift_capacity {round(outlist[2],2)}")
# print(f"kGperkWh_saved {round(outlist[3],2)}")
# print(f"annual_kGCO2_saved {round(outlist[4],2)}")
# print(f"climate_zone CZ{hpwh.getClimateZone()}")
# # simRun_ls.writeCSV('QAHV_test.csv')


# aquaFractLoadUp, aquaFractShed, storageT_F, supplyT_F, loadShiftSchedule, hpwhModel, tmModel, simSchematic, PVol_G_atStorageT, PCap_kW, TMVol_G, TMCap_kW, zipCode, climateZone = 0.21, 0.8, 150, 122, [1,1,1,1,1,1,1,1,0,0,0,0,1,1,1,1,0,0,0,0,0,0,1,1], 'MODELS_ColmacCxA_15_C_SP', 'MODELS_ColmacCxA_20_C_MP', 'paralleltank', 891, 31, 91, 19, 91730,10

# hpwh_ls = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 100,
#             supplyT_F       = supplyT_F,
#             storageT_F      = storageT_F,
#             loadUpT_F       = 150,
#             percentUseable  = 0.9, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = aquaFractLoadUp,
#             aquaFractShed   = aquaFractShed,
#             schematic       = simSchematic, 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 100, 
#             Wapt            = 60,
#             loadShiftSchedule  = loadShiftSchedule,
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.8,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kW,
#             TMVol_G = TMVol_G,
#             TMCap_kW = TMCap_kW,
#             annual = True,
#             zipCode = zipCode,
#             systemModel = hpwhModel,
#             tmModel = tmModel
#         )
# simRunsAndCalcs = hpwh_ls.getSimRunWithkWCalc(initPV=0.4*PVol_G_atStorageT, initST=135)
# simRunsAndCalcs[0].writeCSV('parallel_ls.csv')
# simRunsAndCalcs[1].writeCSV('parallel_nls.csv')

# # print('+++++++++++++++++++++++++++++++++++++++')
# # print('SIZING RESULTS')
# # print('+++++++++++++++++++++++++++++++++++++++')
# TMVol_G = None 
# TMCap_kW = None
# # print('recirc loss', hpwh_for_sizing.building.recirc_loss)
# sizing_result = hpwh_for_sizing.getSizingResults()
# PVol_G_atStorageT = sizing_result[0] 
# PCap_kBTUhr = sizing_result[1] 
# if len(sizing_result) > 2:
#     TMVol_G = sizing_result[2] 
#     TMCap_kW = sizing_result[3]/W_TO_BTUHR
# # print('PVol_G_atStorageT = ',PVol_G_atStorageT)
# # print('PCap_kBTUhr = ',PCap_kBTUhr)
# # print('TMVol_G = ',TMVol_G)
# # print('TMCap_kW = ',TMCap_kW)

# hpwh = EcosizerEngine(
#             incomingT_F     = 33.5,
#             magnitudeStat  = 222.95,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             percentUseable  = 0.85, 
#             aquaFract       = 0.4,
#             schematic       = 'paralleltank', 
#             buildingType   = 'multi_family',
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nBR             = [20, 30, 25, 15, 10, 0],
#             standardGPD     = 'ecoMark',
#             nApt            = 100, 
#             Wapt            = 100,
#             doLoadShift     = False,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kBTUhr/W_TO_BTUHR, 
#             TMVol_G = TMVol_G, 
#             TMCap_kW = TMCap_kW,
#             annual = True,
#             climateZone = 17,
#             systemModel = "MODELS_Mitsubishi_QAHV"
#         )
# simRun = hpwh.getSimRun(minuteIntervals = 60, nDays = 365, exceptOnWaterShortage=False)
# simRun.writeCSV("here.csv")

#########################################################################################################
# rhoCp = 8.353535 
# W_TO_BTUHR = 3.412142
# W_TO_BTUMIN = W_TO_BTUHR/60.
# W_TO_TONS = 0.000284345
# TONS_TO_KBTUHR = 12.
# watt_per_gal_recirc_factor = 100 
# KWH_TO_BTU = 3412.14
# RECIRC_LOSS_MAX_BTUHR = 1080 * (watt_per_gal_recirc_factor * W_TO_BTUHR)


# # regular sizing and 3 day simulation
# aquaFractLoadUp = 0.2
# aquaFractShed   = 0.8
# storageT_F = 150
# loadShiftSchedule        = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,1,1,1] #assume this loadshape for annual simulation every day
# csvCreate = False
# hpwhModel ='MODELS_Mitsubishi_QAHV'
# tmModel ='MODELS_Mitsubishi_QAHV'
# minuteIntervals = 15
# sizingSchematic = 'singlepass_norecirc'
# simSchematic = 'singlepass_rtp'

# def createCSV(simRun : SimulationRun, simSchematic, kGperkWh, loadshift_title, start_vol):
#     csv_filename = f'{simSchematic}_LS_simResult_{hpwhModel}.csv'
#     if loadshift_title == False:
#         csv_filename = f'{simSchematic}_NON_LS_simResult_{hpwhModel}.csv'
#     simRun.writeCSV(csv_filename)

# hpwh_for_sizing = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 150,
#             supplyT_F       = 120,
#             storageT_F      = storageT_F,
#             loadUpT_F       = storageT_F + 10,
#             percentUseable  = 0.85, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = aquaFractLoadUp,
#             aquaFractShed   = aquaFractShed,
#             schematic       = sizingSchematic, 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 110, 
#             Wapt            = 60,
#             loadShiftSchedule        = loadShiftSchedule,
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 1
#         )

# print('+++++++++++++++++++++++++++++++++++++++')
# print('SIZING RESULTS')
# print('+++++++++++++++++++++++++++++++++++++++')
# print('recirc loss', hpwh_for_sizing.building.recirc_loss)
# PVol_G_atStorageT = hpwh_for_sizing.getSizingResults()[0] 
# PCap_kBTUhr = hpwh_for_sizing.getSizingResults()[1] 
# if simSchematic == 'multipass' or simSchematic == 'primaryrecirc':
#     PCap_kBTUhr += (hpwh_for_sizing.building.recirc_loss * 1.75 / 1000)
# print('PVol_G_atStorageT = ',PVol_G_atStorageT)
# print('PCap_kBTUhr = ',PCap_kBTUhr)

# if csvCreate:
#     #test plot output
#     fig = hpwh_for_sizing.plotSizingCurve()
#     fig.write_html('Z:\\sizingplotTEST.html')
# ##########################################################################################
# start_time = time.time()
# simRun_from_sized = hpwh_for_sizing.getSimRun()

# end_time = time.time()
# duration = end_time - start_time
# print("Execution time for simple simulation run:", duration, "seconds")

# print('+++++++++++++++++++++++++++++++++++++++')
# print('SIZING RESULTS')
# print('+++++++++++++++++++++++++++++++++++++++')
# print('recirc loss', hpwh_for_sizing.building.recirc_loss)
# PVol_G_atStorageT = hpwh_for_sizing.getSizingResults()[0] 
# PCap_kBTUhr = hpwh_for_sizing.getSizingResults()[1] 
# if simSchematic == 'multipass' or simSchematic == 'primaryrecirc':
#     PCap_kBTUhr += (hpwh_for_sizing.building.recirc_loss * 1.75 / 1000)
# print('PVol_G_atStorageT = ',PVol_G_atStorageT)
# print('PCap_kBTUhr = ',PCap_kBTUhr)
# print('Vtrig_normal = ',hpwh_for_sizing.system.Vtrig_normal)
# print('Vtrig_shed = ',hpwh_for_sizing.system.Vtrig_shed)
# print('Vtrig_loadUp = ',hpwh_for_sizing.system.Vtrig_loadUp)

# TMVol_G = None
# TMCap_kW = None
# if sizingSchematic == 'swingtank' or sizingSchematic == 'paralleltank':
#     TMVol_G = hpwh_for_sizing.getSizingResults()[2] 
#     TMCap_kW = hpwh_for_sizing.getSizingResults()[3]/W_TO_BTUHR
#     print('TMVol_G = ',TMVol_G)
#     print('TMCap_kW = ',TMCap_kW)
# print('+++++++++++++++++++++++++++++++++++++++')

# # Annual simulation based on sizing from last:

# print("starting LS section using sizes")
# hpwh_ls = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 150,
#             supplyT_F       = 120,
#             storageT_F      = storageT_F,
#             loadUpT_F       = storageT_F + 10,
#             percentUseable  = 1, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = aquaFractLoadUp,
#             aquaFractShed   = aquaFractShed,
#             schematic       = simSchematic, 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 110, 
#             Wapt            = 60,
#             nBR             = [0,50,30,20,0,0],
#             loadShiftSchedule        = loadShiftSchedule,
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.8,
#             PVol_G_atStorageT = PVol_G_atStorageT, 
#             PCap_kW = PCap_kBTUhr/W_TO_BTUHR, 
#             TMVol_G = TMVol_G, 
#             TMCap_kW = TMCap_kW,
#             annual = True,
#             climateZone = 1,
#             systemModel = hpwhModel,
#             tmModel = tmModel
#         )

# start_vol = 0.4*PVol_G_atStorageT
# start_time = time.time()

# simResultArray = hpwh_ls.getSimRunWithkWCalc(initPV=0.4*PVol_G_atStorageT, initST=135, minuteIntervals = minuteIntervals, nDays = 365, optimizeNLS = False)
# lsCap = simResultArray[2]
# print(lsCap)

# # simResultArray = hpwh_ls.getSimRun(minuteIntervals = 1, nDays = 3, optimizeNLS = False)


# end_time = time.time()
# duration = end_time - start_time
# print("Program execution time for annual simulation:", duration, "seconds")

# simRun_ls = simResultArray[0]


# print('=========================================================')
# print('average city watertemp is', simRun_ls.getAvgIncomingWaterT())
# print('=======================FOR LS============================')
# loadshift_capacity = simResultArray[2]
# kGperkWh = simRun_ls.getkGCO2Sum()/loadshift_capacity
# print('ls kg_sum is', simRun_ls.getkGCO2Sum())
# print('ls kGperkWh is', kGperkWh)
# print('annual COP:', simRun_ls.getAnnualCOP())
# print('annual COP (boundry):', simRun_ls.getAnnualCOP(True))

# if csvCreate:
#     createCSV(simRun_ls, simSchematic, kGperkWh, True, start_vol)

# print('=====================FOR NON LS==========================')
# simRun_nls = simResultArray[1]

# kGperkWh_nonLS = simRun_nls.getkGCO2Sum()/loadshift_capacity
# print('non-ls kg_sum is', simRun_nls.getkGCO2Sum())
# print('non-ls kGperkWh is', kGperkWh_nonLS)
# print('annual COP:', simRun_nls.getAnnualCOP())
# print('annual COP (boundry):', simRun_nls.getAnnualCOP(True))

# # if csvCreate:
# #     createCSV(simRun_nls, simSchematic, kGperkWh_nonLS, False, start_vol)
# print('=========================================================')
# print("LS to non-LS diff:", kGperkWh_nonLS - kGperkWh, "=", simResultArray[3])


##############################################################################################
# # PVol_G_atStorageT = 400
# print("starting LS section using sizes")
# loadshape = [18.52, 32.27, 11.51, 9.96, 19.01, 51.56, 324.4, 339.9, 308.27, 198.04, 373.78, 259.31, 195.34, 294.24, 345.65, 441.84, 310.58, 417.3, 330.08, 96.58, 10.62, 12.03, 14.5, 27.32]
# loadshape = [math.ceil(x) for x in loadshape]
# totalDemand = sum(loadshape)
# print('total HW demand', totalDemand)
# normalizedLoad = [x / sum(loadshape) for x in loadshape]
# print('normalized Load', normalizedLoad)
# nPep = 200
# vol = nPep * 6
# kbtu = nPep * 0.8
# hpwh = EcosizerEngine(
#                      incomingT_F     = 50,
#                      magnitudeStat  = nPep,
#                      supplyT_F       = 120,
#                      storageT_F      = 150,
#                      percentUseable  = 0.9,
#                      aquaFract       = 0.4,
#                      schematic       = "singlepass_rtp",
#                      buildingType   = 'multi_family',
#                      flowRate       = 0,
#                      gpdpp           = 25,
#                      safetyTM        = 1.75,
#                      defrostFactor   = 1,
#                      compRuntime_hr  = 16,
#                      nApt            = int(100),
#                      Wapt            = int(60),
#                      loadShiftSchedule = [1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,0,0,0,0,1],
#                      loadUpHours     = int(3),
#                      doLoadShift     = True,
#                      loadShiftPercent= 0.95,
#                      aquaFractLoadUp = 0.2,
#                      aquaFractShed   = 0.8,
#                      loadUpT_F       = 160,
#                      PVol_G_atStorageT = vol,
#                      PCap_kW =  kbtu / 3.41,
#                      TMVol_G = TMVol_G,
#                      TMCap_kW = TMCap_kW,
#                      annual = True,
#                      climateZone = 1,
#                      systemModel = "MODELS_Mitsubishi_QAHV")

# start_vol = vol
# start_time = time.time()

# simRun_ls = hpwh.getSimRun(initPV=start_vol, initST=135, minuteIntervals = minuteIntervals, nDays = 365, exceptOnWaterShortage = False)

# end_time = time.time()
# duration = end_time - start_time
# print("Program execution time for annual simulation:", duration, "seconds")

# if csvCreate:
#     csv_filename = f'{simSchematic}_thing_simResult_{hpwhModel}.csv'
#     simRun_ls.writeCSV(csv_filename)

###################################################################################################################################################

# swing_sizer = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 90,
#             supplyT_F       = 120,
#             storageT_F      = 149,
#             loadUpT_F       = 159,
#             percentUseable  = 0.95, 
#             aquaFract       = 0.4, 
#             aquaFractLoadUp = 0.2,
#             aquaFractShed   = 0.8,
#             schematic       = 'multipass_norecirc', 
#             buildingType   = 'multi_family',
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1,
#             compRuntime_hr  = 16, 
#             nApt            = 85, 
#             Wapt            = 60,
#             loadShiftSchedule        = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0],
#             loadUpHours     = 3,
#             doLoadShift     = True,
#             loadShiftPercent       = 0.95,
#             PVol_G_atStorageT= 2000,
#             numHeatPumps= 4,
#             systemModel="MODELS_ColmacCxA_20_MP",
#             annual=True,
#             zipCode=90001
#         )
# simResult = swing_sizer.getSimRun(minuteIntervals=15,nDays=365)
# print(simResult.LS_sched)
# # print(simResult[0][:10])
# # print(simResult[1][-10:])
# # print(simResult[2][-65:-55])
# # print(simResult[3][800:810])
# # print(simResult[4][-10:-4])
# # print(simResult[5][-200:-190])
# # print(simResult[6][800:803])
# print("===============================================")
#print(hpwh.plotStorageLoadSim(minuteIntervals = 15, nDays = 365, return_as_div = False))
# parallel_sizer = EcosizerEngine(
#             incomingT_F     = 50,
#             magnitudeStat  = 500,
#             supplyT_F       = 120,
#             storageT_F      = 150,
#             percentUseable  = 0.9, 
#             aquaFract       = 0.4, 
#             schematic       = 'swingtank', 
#             buildingType   = 'multi_family',
#             returnT_F       = 0, 
#             flowRate       = 0,
#             gpdpp           = 25,
#             safetyTM        = 1.75,
#             defrostFactor   = 1, 
#             compRuntime_hr  = 16, 
#             nApt            = 351, 
#             Wapt            = 100,
#             doLoadShift     = False,
#         )




