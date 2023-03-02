from objects.Building import *

def create_building(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic, building_type, other_vars = None):
    match building_type:
        case 'apartment':
            return Apartment(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'elementary_school':
            return ElementarySchool(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'food_service_a':
            return FoodServiceA(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'food_service_b':
            return FoodServiceB(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'junior_high':
            return JuniorHigh(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'mens_dorm':
            return MensDorm(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'motel':
            return Motel(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'nursing_home':
            return NursingHome(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'office_building':
            return OfficeBuilding(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'senior_high':
            return SeniorHigh(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'womens_dorm':
            return WomensDorm(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic)
        case 'multi_family':
            if not other_vars or len(other_vars) < 3 or len(other_vars) > 4:
                print('error here')
                # TODO error
            else:
                return MultiFamily(hot_water_temp, city_water_temp, return_water_temp, flow_rate, magnitude_statistic, *other_vars)
        case _:
            return 'error?' # TODO handle error
