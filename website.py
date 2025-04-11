from weakref import ref
from .risk_assessment_library import risk_assessment_library
from .document import document
from flask import Flask,render_template,request,flash,session,redirect
import time 
import os
import psutil 
from datetime import datetime
import pandas as pd 
import random
import subprocess 
from subprocess import Popen
import numpy as np

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

class website():
    return_string = ""
    def __init__(self,id,place=None):
        self.id = id
        self.place = place
        self.ra = risk_assessment_library(id,place)
        self.return_string = ""

    def predicting_W_value(self,MFI_value,RSI_value,K_value,D_value):
        temp_list = np.array([])
        temp_list = np.append(temp_list,MFI_value)
        temp_list = np.append(temp_list,RSI_value)
        temp_list = np.append(temp_list,K_value)
        predicting_W_moderate = 1/2 * 0.618**2*np.max(temp_list) + 1/2 * np.min(temp_list) + 1/2*0.618*np.median(temp_list)
        predicting_W_sell = 1/2 * 0.618**2*np.min(temp_list) + 1/2 * np.max(temp_list) + 1/2*0.618*np.median(temp_list)
        return predicting_W_moderate, predicting_W_sell

    def prediction_reflection(self):
        list_of_5_days = np.array([])
        number_of_5_days = 0
        list_of_10_days = np.array([])
        number_of_10_days = 0
        list_of_15_days = np.array([])
        number_of_15_days = 0
        reference_point = 0
        list_of_reflection2= np.array([])
        j_list = np.array([])
        average_day_list= np.array([])
        return_string = ""

        ## Sorting alrogithms 
        ## For checking for the rise of W moderate value
        for i in self.ra.list_of_reflection:
            if (i+1 >=len(self.ra.W_moderate_list_within_class)):
                list_of_reflection2 = np.append(list_of_reflection2,i)
                break

            if (self.ra.W_moderate_list_within_class[i+1] > 17):
                list_of_reflection2 = np.append(list_of_reflection2,i)
                break

        return_string +="\n"

        ## the time complexity is O(15*n) = O(n) so like if we reduce the time complexity 
        ## to O(root n) then we can make it faster
        for i in list_of_reflection2:
            for j in range(15):
                if (i+j>= len(self.ra.W_moderate_list_within_class)):
                    return_string +="Gone\n"
                    break
                if (self.ra.W_moderate_list_within_class[i+j] -self.ra.W_moderate_list_within_class[i] > 7.5 and j<=5):
                    return_string += "\n5 days result\n"
                    for k in range(j):
                        return_string += f"{self.ra.list_of_date[i+k]}\n"
                    
                    return_string += f"Date taken:{j}\n"
                    return_string+="The previous days W_moderate"
                    for k in range(j):
                        return_string += f"{self.ra.W_moderate_list_within_class[i+k]}\n"
                    return_string+=f"\nEnding point W_moderate:{self.ra.W_moderate_list_within_class[i+j]}\n"
                    return_string+=f"Ending date:{self.ra.list_of_date[i+j+13]}\n"
                    j_list = np.append(j_list,j)
                    if (i- reference_point<=5):
                        reference_point = i
                        break
                    list_of_5_days = np.append(list_of_5_days,i)
                    number_of_5_days += 1
                    break
                elif (self.ra.W_moderate_list_within_class[i+j] -self.ra.W_moderate_list_within_class[i] > 7.5 and j<=10):
                    return_string += "\n10 days result\n"
                    for k in range(j):
                        return_string += f"{self.ra.list_of_date[i+k]}\n"
                    
                    return_string += f"Date taken:{j}\n"
                    return_string+="The previous days W_moderate"
                    for k in range(j):
                        return_string += f"{self.ra.W_moderate_list_within_class[i+k]}\n"
                    return_string+=f"\nEnding point W_moderate:{self.ra.W_moderate_list_within_class[i+j]}\n"
                    return_string+=f"Ending date:{self.ra.list_of_date[i+j+13]}\n"
                    j_list = np.append(j_list,j)
                    if (i- reference_point<=10):
                        reference_point = i
                        break
                    list_of_10_days = np.append(list_of_10_days,i)
                    number_of_10_days += 1
                    break
                elif (self.ra.W_moderate_list_within_class[i+j] -self.ra.W_moderate_list_within_class[i] > 7.5 and j<=15):
                    return_string += "\n15 days result\n"
                    for k in range(j):
                        return_string += f"{self.ra.list_of_date[i+k]}\n"
                    
                    return_string += f"Date taken:{j}\n"
                    return_string+="The previous days W_moderate"
                    for k in range(j):
                        return_string += f"{self.ra.W_moderate_list_within_class[i+k]}\n"
                    return_string+=f"\nEnding point W_moderate:{self.ra.W_moderate_list_within_class[i+j]}\n"
                    return_string+=f"Ending date:{self.ra.list_of_date[i+j+13]}\n"
                    j_list = np.append(j_list,j)
                    if (i- reference_point<=15):
                        reference_point = i
                        break
                    list_of_15_days = np.append(list_of_15_days,i)
                    number_of_15_days += 1
                    break

        ## Printing result after sorting
        for i in range(len(list_of_reflection2)):
            if i+1 == len(list_of_reflection2):
                break

            average_day_list = np.append(average_day_list,self.ra.calucate_elasped_days(self.ra.list_of_date[list_of_reflection2[i]+self.a],self.ra.list_of_date[list_of_reflection2[i+1]+self.ra.a]))

        self.elasped_day_list = average_day_list

        return_string = "The analysis result: \n"

        if list_of_5_days:
            return_string += "5 days:\n"
            for i in range(list_of_5_days):
                return_string += f"{self.ra.list_of_date[list_of_5_days[i]]}\n"
        
        if list_of_10_days:
            return_string += "10 days:\n"
            for i in range(list_of_10_days):
                return_string += f"{self.ra.list_of_date[list_of_10_days[i]]}\n"

        if list_of_15_days:
            return_string += "15 days:\n"
            for i in range(list_of_15_days):
                return_string += f"{self.ra.list_of_date[list_of_15_days[i]]}\n"

        return_string += f"The number of 5 days: {number_of_5_days}\n"
        return_string += f"The number of 10 days: {number_of_10_days}\n"
        return_string += f"The number of 15 days: {number_of_15_days}\n"

        return_string += "\nOn average:\n"
        return_string += f"We need to wait {np.mean(j_list)} days to see a rebound\n"
        return_string += f"Between each reflection, we need to wait {np.mean(average_day_list)} days\n"
        return_string += f"and the standard deviation is {np.std(average_day_list)}\n"
        return return_string

    
    def requesting_one_agpd(self):
        self.return_string = f"W_buy_at_that_point: {self.ra.W_moderate_list_within_class[-1]} \n W_sell at that day: {self.ra.W_sell_list[-1]}"  
        self.return_string += "\n\n The other details:"
        self.return_string += f"\nThe targetted ag value: {self.ra.ag} \n The targetted agpd value :{self.ra.agpd}\n"
        self.return_string += f"\nThe targetted number of trade value: {self.ra.number_of_trade}\n"
        self.return_string += self.prediction_reflection()
        ## missing predicting Z_5 list and Z_15 list
        self.ra.close()

        return self.return_string
    
    def price_when_w_is_reach_to_certain_value(self,target_value:float,buy_or_sell:bool):
        '''
        This function is used to check the price when the W_moderate value is reached to a certain value

        Input Parameters:
        target_value: The value of W_moderate that we want to reach
        buy_or_sell: Checking if it is buying or selling 
                    default buying is positive and selling is negative
        
        '''
        ## The target value is the value of W_moderate that we want
        w_moderate_trying = 0 
        W_sell_trying = 0
        result_string = ""
    
        if target_value < 0 or target_value > 100:
            raise ValueError("The value should be between 0 and 100")
        ## Check if the value is 
        rsv_value = self.ra.rsi_list[-1]
        k_value = self.ra.k_value_list[-1]
        d_list = self.ra.d_list[-1]
        mfi_value = self.ra.mfi_list[-1]
        w_moderate = self.ra.W_moderate_list_within_class[-1]
        w_sell = self.ra.W_sell_list[-1]

        if (buy_or_sell == True):
            ## meaning that we want to buy and use the buying value
            w_moderate_trying = w_moderate
            percetnage = 1

            while (w_moderate_trying < target_value):
                
                ## need to get the ending price 
                presumable_price = self.ra.list_of_ending_price[-1]
                persumable_price = persumable_price*percetnage
                self.ra.close()
                self.ra = risk_assessment_library(self.id,self.place)
                w_moderate_trying = target_value
                self.ra.list_of_ending_price = np.append(self.ra.list_of_ending_price,persumable_price)
                self.ra.re_work()
                percentage += 0.01
        else:
            ## meaning that we want to sell and use the selling value
            w_sell_trying = w_sell
            percentage = 1

            while (w_sell_trying < target_value):
                presumable_price = self.ra.list_of_ending_price[-1]
                presumable_price = presumable_price*percentage
                self.ra.close()
                self.ra = risk_assessment_library(self.id,self.place)
                w_sell_trying = target_value
                self.ra.list_of_ending_price = np.append(self.ra.list_of_ending_price,presumable_price)
                self.ra.re_work()
                percentage -= 0.01

        result_string = f"If W value is risen to the {target_value} then the price will be {self.ra.list_of_ending_price[-1]} and the percentage change from current price is {percentage}\n"

        return result_string
    










    

