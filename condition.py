import logging
from abc import ABC, abstractmethod
import datetime

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class Condition(ABC):
    @abstractmethod
    def evaluate(self, patient_age, patient_gender, lab_values):
        pass

    @staticmethod
    def from_dict(condition_data):
        condition_type = condition_data.get('type')
        if condition_type == 'timedependent':
            condition_type = 'time-dependent'

        if condition_type == 'range':
            return RangeCondition(condition_data)
        elif condition_type == 'comparison':
            return ComparisonCondition(condition_data)
        elif condition_type == 'time-dependent':
            return TimeDependentCondition(condition_data)
        else:
            raise ValueError(f"Unknown condition type: {condition_type}")

    def to_dict(self):
        return {
            'type': self.__class__.__name__.lower().replace('condition', ''),
            'parameter': self.parameter,
            'unit': self.unit,
            'age_min': self.age_min,
            'age_max': self.age_max,
            'gender': self.gender
        }

class RangeCondition(Condition):
    def __init__(self, condition_data):
        self.min_value = condition_data.get('min_value')
        self.max_value = condition_data.get('max_value')
        self.parameter = condition_data.get('parameter')
        self.unit = condition_data.get('unit')
        self.age_min = condition_data.get('age_min')
        self.age_max = condition_data.get('age_max')
        self.gender = condition_data.get('gender')

    def evaluate(self, patient_age, patient_gender, lab_values):
        if not (self.age_min <= patient_age <= self.age_max):
            return False
        if self.gender != 'all' and self.gender != patient_gender:
            return False

        for lab_value in lab_values:
            if lab_value['parameter_name'].lower() == self.parameter.lower() and lab_value['valid_until'] >= str(datetime.date.today()):
                if self.min_value <= lab_value['value'] <= self.max_value:
                    return True
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'min_value': self.min_value,
            'max_value': self.max_value
        })
        return data

class ComparisonCondition(Condition):
    def __init__(self, condition_data):
        self.operator = condition_data.get('operator')
        self.comparison_value = condition_data.get('comparison_value')
        self.parameter = condition_data.get('parameter')
        self.unit = condition_data.get('unit')
        self.age_min = condition_data.get('age_min')
        self.age_max = condition_data.get('age_max')
        self.gender = condition_data.get('gender')

    def evaluate(self, patient_age, patient_gender, lab_values):
        if not (self.age_min <= patient_age <= self.age_max):
            return False
        if self.gender != 'all' and self.gender != patient_gender:
            return False

        for lab_value in lab_values:
            if lab_value['parameter_name'].lower() == self.parameter.lower() and lab_value['valid_until'] >= str(datetime.date.today()):
                if self.compare_values(lab_value['value']):
                    return True
        return False

    def compare_values(self, value):
        if self.operator == 'greater':
            return value > self.comparison_value
        elif self.operator == 'less':
            return value < self.comparison_value
        elif self.operator == 'equal':
            return value == self.comparison_value
        elif self.operator == 'greater or equal':
            return value >= self.comparison_value
        elif self.operator == 'less or equal':
            return value <= self.comparison_value
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'operator': self.operator,
            'comparison_value': self.comparison_value
        })
        return data

class TimeDependentCondition(Condition):
    def __init__(self, condition_data):
        self.operator = condition_data.get('operator')
        self.comparison_time_value = condition_data.get('comparison_time_value')
        self.time = condition_data.get('time')
        self.parameter = condition_data.get('parameter')
        self.unit = condition_data.get('unit')
        self.age_min = condition_data.get('age_min')
        self.age_max = condition_data.get('age_max')
        self.gender = condition_data.get('gender')

    def evaluate(self, patient_age, patient_gender, lab_values):
        logging.debug(f"Evaluating TimeDependentCondition for patient age: {patient_age}, gender: {patient_gender}")
        
        if not (self.age_min <= patient_age <= self.age_max):
            logging.debug(f"Patient age {patient_age} is outside the range [{self.age_min}, {self.age_max}]")
            return False
        if self.gender != 'all' and self.gender != patient_gender:
            logging.debug(f"Patient gender {patient_gender} does not match condition gender {self.gender}")
            return False

        relevant_lab_values = [
            lv for lv in lab_values
            if lv['parameter_name'].lower() == self.parameter.lower()
        ]

        logging.debug(f"Found {len(relevant_lab_values)} relevant lab values for parameter {self.parameter}")

        relevant_lab_values.sort(key=lambda x: datetime.datetime.strptime(x['time'], '%Y-%m-%d'))

        if len(relevant_lab_values) < 2:
            logging.debug("Less than 2 relevant lab values found, cannot evaluate time-dependent condition")
            return False

        for i in range(len(relevant_lab_values) - 1):
            for j in range(i + 1, len(relevant_lab_values)):
                time_diff = (datetime.datetime.strptime(relevant_lab_values[j]['time'], '%Y-%m-%d') -
                             datetime.datetime.strptime(relevant_lab_values[i]['time'], '%Y-%m-%d')).days

                logging.debug(f"Comparing lab values at times {relevant_lab_values[i]['time']} and {relevant_lab_values[j]['time']}, time difference: {time_diff} days")

                if time_diff >= int(self.time):
                    if self.compare_values(relevant_lab_values[i]['value']) and \
                       self.compare_values(relevant_lab_values[j]['value']):
                        logging.debug("Time-dependent condition met")
                        return True
        logging.debug("Time-dependent condition not met")
        return False

    def compare_values(self, value):
        if self.operator == 'greater':
            return value > self.comparison_time_value
        elif self.operator == 'less':
            return value < self.comparison_time_value
        elif self.operator == 'equal':
            return value == self.comparison_time_value
        elif self.operator == 'greater or equal':
            return value >= self.comparison_time_value
        elif self.operator == 'less or equal':
            return value <= self.comparison_time_value
        return False

    def to_dict(self):
        data = super().to_dict()
        data.update({
            'operator': self.operator,
            'comparison_time_value': self.comparison_time_value,
            'time': self.time
        })
        return data