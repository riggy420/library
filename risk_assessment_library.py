from hmac import new
import math
import pandas as pd
import csv
import numpy as np
import time
from selenium import webdriver
from bs4 import BeautifulSoup
import math
import time
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from datetime import datetime
from datetime import datetime,timedelta
# from numba import jit, cuda
import numpy as np
import yfinance as yf
from pandas_datareader import data as pdr
# from fake_useragent import UserAgent
from datetime import datetime
import requests
import urllib.parse
import requests 
import urllib


class risk_assessment_library:
    '''
    This is the main class for risk_assessment_library

    From here, we are calucating the W_moderate value and w_sell value as an indicator

    For the W_sell value, we are using the following equation:

    W_sell = *1/2* * 0.618^{2} * min(MFI,RSI,D)+1/2 * max(MFI,RSI,D)+1/2*0.618 * median(MFI,RSI,D)

    For the W_moderate value, we are using the following equation:

    W_moderate = *1/2* * 0.618^{2} * max(MFI,RSI,D)+1/2 * min(MFI,RSI,D)+1/2*0.618 * median(MFI,RSI,D)

    The W_sell value is used to calucate the sell signal
    The W_moderate value is used to calucate the buy signal

    Besides, the function will return the following value and stored them as a list
    1. MFI value (list_of_MFI)
    2. RSI value (rsi_list)
    3. K value (list_of_k_value)
    4. D value (list_of_d_value)
    5. W_moderate value (W_moderate_list)
    6. W_sell value (W_sell_list)
    7. AGPD value (agpd)
    8. Number of trade (number_of_trade)
    9. Average day (average_day)
    10. Day standard deviation (day_std_deviation)
    11. Revenue per year (revenue_per_year)
    12. Average volume (average_volume)
    13. Elasped days (elasped_day)
    14. Total cost (total_cost)
    15. Total revenue (total_revenue)
    16. Total elasped days (total_elasped_day)
    17. Total cost value (total_cost_value)
    18. Total revenue value (total_revenue_value)

    Basic information of the stock is stored in the following list:
    1. List of opening price (list_of_opening_price)
    2. List of maximum price (list_of_maximum_price)
    3. List of minimum price (list_of_minimum_price)
    4. List of volume of exchange (list_of_volume_of_exchange)
    5. List of date (list_of_date)
    6. List of ending price (list_of_ending_price)
    7. List of rate of change (list_of_rate_of_change)
    8. List of volume of exchange hand (list_of_volume_of_exchange_hand)
    9. List of rate of change in float (list_of_rate_of_change_in_float)
    10. List of volume exceed (list_of_volume_exceed)   

    With that said, it should return the object with everything installed:

    For example, how we can call the object:

    .. highlight:: python
    .. code-block:: python
        from risk_assessment_library import risk_assessment_library
        r = risk_assessment_library("AAPL")
        print(r.W_moderate_list)
    '''
    list_of_opening_price = np.array([],dtype=np.float64) ## initial value for list of opening price
    list_of_maximum_price = np.array([],dtype=np.float64) ## initial value for list of maximum price
    list_of_minimum_price = np.array([],dtype=np.float64) ## initial value for list of minimum price
    list_of_volume_of_exchange = np.array([],dtype=np.float64) ## initial value for list of volume of exchange
    alpha = 2/15 ## the mutiplier for ema values 
    ema_value = 30 ## initial value for ema
    price = 0 ## initial value for price
    date = 0 ## initial value for date
    date_14 = 0 ## initial value for date_14
    k_value = 50 ## initial value for k value
    list_of_date = np.array([]) ## initial value for list of date
    list_of_ending_price = np.array([],dtype=np.float64) ## initial value for list of ending price
    list_of_rsv = np.array([],dtype=np.float64) ## initial value for list of rsv
    list_of_k_value = np.array([],dtype=np.float64) ## initial value for list of k value
    list_of_d_value = np.array([],dtype=np.float64) ## initial value for list of d value
    d_value = 50 ## initial value for d value
    list_of_MFI = np.array([]) ## initial value for list of MFI
    sum_of_positive_ema_value = 0 
    sum_of_negative_ema_value = 0
    list_of_volume_exceed = np.array([],dtype=np.float64) ## initial value for list of volume exceed
    list_of_rate_of_change = np.array([],dtype=np.float64) ## initial value for list of volume
    list_after_editing = np.array([],dtype=np.float64) ## initial value for list after editing
    list_of_volume_of_exchange_hand = np.array([],dtype=np.float64) ## initial value for list of volume of exchange hand
    list_of_rate_of_change_in_float = np.array([],dtype=np.float64) ## initial value for list of rate of change in float
    up = np.array([],dtype=np.float64) ## initial value for up
    down = np.array([],dtype=np.float64) ## initial value for down
    ema_list = np.array([],dtype=np.float64) ## initial value for ema list
    ema_up = 0
    ema_down = 0
    rsi_list = np.array([],dtype=np.float64) ## initial value for rsi list
    W_list = np.array([],dtype=np.float64) ## initial value for W list
    W_value = 0
    a = 0 
    mfr = 0
    comparing_date_purchase = np.array([],dtype=np.float64) #: the indices of the purchase date in the list of_date to comparing date purchase
    comparing_date_sell_off = np.array([],dtype=np.float64) #: the indices of the date that we ought to sell off to the comparing date sell off
    strings = np.array([],dtype=np.float64) ## initial value for strings
    x =0
    actual_purchase = np.array([],dtype=np.float64) ## initial value for actual purchase
    actual_sell_off = np.array([],dtype=np.float64) ## initial value for actual sell off
    removal = 0 
    actual_actual_purchase = np.array([],dtype=np.float64) ## initial value for actual actual purchase
    total_cost = np.array([],dtype=np.float64) ## initial value for total cost
    total_revenue =np.array([],dtype=np.float64) ## initial value for total revenue
    elasped_day = np.array([],dtype=np.float64) ## initial value for elasped day
    number_of_trade = 0
    total_cost_value= 0
    total_revenue_value =0
    total_elasped_day= 0 
    ag = 0
    agpd=0
    revenue_per_year = 0
    average_volume = 0
    buy_at_ending_price = np.array([],dtype=np.float64) ## initial value for buy at ending price
    sell_at_ending_price =np.array([],dtype=np.float64) ## initial value for sell at ending price
    current_price =0 
    current_price_list = np.array([],dtype=np.float64) ## initial value for current price list
    list_of_reflection = np.array([],dtype=np.float64) ## initial value for list of reflection
    W_moderate_list_within_class=np.array([],dtype=np.float64) ## initial value for W moderate list within class
    elasped_day_list = np.array([],dtype=np.float64) ## initial value for elasped day list
    W_sell_list_within_class = np.array([],dtype=np.float64) ## initial value for W sell list within class
    winrate = 0 ## initial value for winrate
    average_day = 0 ## initial value for average day

    def __init__(self,name,area=""):
        '''
        This is the initialisation of risk_assessment_library
        
        Idealy, we only need to write out the name of the code and spectify the area that we should be in and everything should be loaded. It didn't happen in the past so

        Parameters:
        ----------
        name `(str)`: the name of the stock that we are looking for
        area `(str)`: the area that we are looking for

        Returns:
        ----------
        The finihsed object that we have finished loading the data
        '''
        self.close() ### clearing the file first => Idk why can have error if you are spamming it for too long time
        self.name=name ## idetnifier for the object
        if area == "industry" : ## if you are doing the overivew of the industry => Probably go here
            self.area = "industry" ## remove the area tag 
            stock_price_database = "/home/ricky/Documents/china_stock_industry_catego/{}.xlsx".format(self.name)
            self.data = pd.ExcelFile(stock_price_database).parse()
            
        else:
            if area != "": ### if it is China stock => Unique idenitifer => SS,SZ can expand to others like jp ..
                self.area= area
                stock_price_database = r"stock_data/{}/{}.{}.txt".format(self.area,self.name,self.area)
            else:
                self.area= "America"
                stock_price_database = r"stock_data/America/{}.txt".format(self.name)

        f=open(stock_price_database,'r',encoding="utf8") ### opening the files 
        self.strings = f.read().split("\n") ## reading the individual content of the file
        self.strings = self.strings[:-1] ## remove the last white space => sometimes it will hinder the understanding
        
        if self.area == "industry": ## since we are using akshare => that is their ways of doing it
            num_of_data = self.split_string_for_industry()
        else:
            num_of_data = self.split_string()

        if num_of_data == 10: ## filter the stocks with not enough data
            self.agpd = -100
            raise Exception("Not enough data")
        
        self.get_date() ## getting the date 
        self.RSV()  ## getting the rsv list
        self.rsi_list = self.ema() ##  running through ema function to get the rsi function 
        self.K()  ## running the k forumla
        self.d_list = self.D() ## running the d forumla
        self.MFI_list = self.MFI_list1() ## running MFI list as well
        self.W_moderate_list,self.W_sell_list = self.W_moderate() ## combining and running thr W moderate forumla 
        # print(self.W_moderate_list_within_class)
        self.ag, self.agpd,self.number_of_trade,self.average_day, self.day_std_deviation,self.revenue_per_year = self.income() ## doing the final analysis and testing it through the past data by adding the virtual money and see
        self.average_volume = np.mean(self.list_of_volume_of_exchange)*self.list_of_ending_price[-1]  ## calucating the average of all
        # self.close()

    def split_string(self):
        '''
        This is the function that we use to split the string
        No need for the input or output
        '''
        for string in self.strings:
            string = string.replace('"','')
            string12 = string.split(",", 5)
            # print(string12)
            string12[0]=string12[0][:10]

            self.list_of_date=np.append(self.list_of_date,string12[0])
            self.list_of_ending_price=np.append(self.list_of_ending_price,float(string12[1]))
            self.list_of_opening_price=np.append(self.list_of_opening_price,float(string12[4]))
            self.list_of_maximum_price=np.append(self.list_of_maximum_price,float(string12[2]))
            self.list_of_minimum_price=np.append(self.list_of_minimum_price,float(string12[3]))
            self.list_of_volume_of_exchange=np.append(self.list_of_volume_of_exchange,float(string12[5]))
        
        if (len(self.list_of_date)<28):
            return 10
        else: 
            return 1
        
    def split_string_for_industry(self):
        '''
        This is the function that we use to split the string
        No need for the input or output
        It is spectifically for the indistry
        '''
        for ind in self.data.index:
            self.list_of_date=np.append(self.list_of_date,self.data['日期'][ind])
            self.list_of_ending_price=np.append(self.list_of_ending_price,self.data['收盘'][ind])
            self.list_of_opening_price=np.append(self.list_of_opening_price,self.data['开盘'][ind])
            self.list_of_maximum_price=np.append(self.list_of_maximum_price,self.data['最高'][ind])
            self.list_of_minimum_price=np.append(self.list_of_minimum_price,self.data['最低'][ind])
            self.list_of_volume_of_exchange=np.append(self.list_of_volume_of_exchange,self.data['成交量'][ind])
            self.list_of_rate_of_change=np.append(self.list_of_rate_of_change,self.data['涨跌幅'][ind])
            self.list_of_volume_of_exchange=np.append(self.list_of_volume_of_exchange_hand,self.data['成交额'][ind])

        if (len(self.list_of_date)<28):
            return 10
        else:
            return 1
        
    def reverse(self):
        '''
        This is the function that we use to reverse the list
        '''
        self.list_of_date = np.flip(self.list_of_date)
        self.list_of_ending_price = np.flip(self.list_of_ending_price)
        self.list_of_opening_price = np.flip(self.list_of_opening_price)
        self.list_of_maximum_price = np.flip(self.list_of_maximum_price)
        self.list_of_minimum_price = np.flip(self.list_of_minimum_price)
        self.list_of_volume_of_exchange = np.flip(self.list_of_volume_of_exchange)
        self.list_of_rate_of_change = np.flip(self.list_of_rate_of_change)
        self.list_of_volume_of_exchange_hand = np.flip(self.list_of_volume_of_exchange_hand)
    
    def get_date(self):
        '''
        This is the function that we use to get the date or reset the mutiplier for self.list_of_date and the W_moderate value
        '''
        self.x=self.a=13

    def MFI(self):
        '''
        This is the function that we use to calculate the MFI value

        Parameters(Inputs):
        ----------
        self => in fact, we will start from the beginning of the list (of closing price)

        Returns:
        ----------
        MFI_value `(float)`: the value of the MFI for 14 days
        '''
        money_positve_flow = np.array([]) ## making the array for calucating the money positive flow
        money_negative_flow = np.array([]) ## making the array for calucating the money negative flow

        for i in range(14):
            max_value = self.list_of_maximum_price[i+self.x-13]
            min_value = self.list_of_minimum_price[i+self.x-13]

            if (self.list_of_ending_price[i+self.x-13] > self.list_of_ending_price[i+self.x-14]):
                typical_price = (max_value+min_value+self.list_of_ending_price[i+self.x-13])/3
                raw_money = typical_price*self.list_of_volume_of_exchange[i+self.x-13]
                money_positve_flow = np.append(money_positve_flow,raw_money)
            else:
                typical_price = (max_value+min_value+self.list_of_ending_price[i+self.x-13])/3
                raw_money = typical_price*self.list_of_volume_of_exchange[i+self.x-13]
                money_negative_flow = np.append(money_negative_flow,raw_money)

        total_postive_flow = np.sum(money_positve_flow)
        total_negative_flow = np.sum(money_negative_flow)

        if total_negative_flow == 0:
            mfr = 1000000000000
        else:
            mfr = total_postive_flow/total_negative_flow

        MFI_value = 100*(1-1/(1+mfr))
        return MFI_value
    
    def MFI_list1(self):
        '''
        This is the function that we use to calculate the MFI value and turn it into a list rather than a value

        Parameters(Inputs):
        ----------
        self

        Returns:
        ----------
        MFI_value `(lsist[float])`: the list of MFI value
        '''
        for i in range(len(self.list_of_ending_price)-13):
            y = self.MFI()
            self.list_of_MFI=np.append(self.list_of_MFI,y)
            self.x+=1

        return self.list_of_MFI
    
    def ema(self):
        '''
        This is the function that we use to calculate the ema value

        Parameters(Inputs):
        ----------
        self

        Returns:
        ----------
        rsi `(list[float])`: the value of the rsi
        '''
        for i in range(1,len(self.list_of_ending_price)):
            if (self.list_of_ending_price[i-1]>self.list_of_ending_price[i+1-1]):
                self.down = np.append(self.down,np.array([self.list_of_ending_price[i-1] - self.list_of_ending_price[i+1-1]]))
                # self.down +=[self.list_of_ending_price[i-1] - self.list_of_ending_price[i+1-1] ] # need to minus 1 for some reason
                self.up = np.append(self.up,0)
            elif (self.list_of_ending_price[i-1]<self.list_of_ending_price[i+1-1]):
                self.up=np.append(self.up,np.array([self.list_of_ending_price[i+1-1] - self.list_of_ending_price[i-1]]))
                # self.up += [self.list_of_ending_price[i+1-1] - self.list_of_ending_price[i-1]]
                self.down = np.append(self.down,0)
            else:
                self.up=np.append(self.up,0)
                self.down=np.append(self.down,0)

        ema_up = 0
        ema_down = 0
        sum_ema_up_list = np.array([],dtype=np.float32)
        sum_ema_down_list = np.array([],dtype=np.float32)

        for i in range(14):
            ema_up += self.up[i]*(1-self.alpha) ** (i)
            sum_ema_up_list=np.append(sum_ema_up_list,ema_up)
            ema_down += self.down[i]*(1-self.alpha) ** (i)
            sum_ema_down_list=np.append(sum_ema_down_list,ema_down)

        ema_up = ema_up/14
        ema_down = ema_down/14

        # print(len(self.up))

        for i in range(len(self.up)-self.x-1):
            ema_up = self.alpha*self.up[self.x+i+1] +(1-self.alpha)*ema_up  #orginally i+12
            ema_down = self.alpha*self.down[self.x+i+1] +(1-self.alpha)*ema_down

            if ema_down == 0:
                ema_down = 1/10000
                rs = ema_up/ema_down
            else:
                rs = ema_up/ema_down

            rsi = (1-(1/(1+rs)))*100
            self.rsi_list=np.append(self.rsi_list,rsi)

        return self.rsi_list
    
    def RSV(self):
        '''
        This is the function that we use to calculate the RSV value

        Parameters(Inputs):
        ----------
        self

        Returns:
        ----------
        list_of_rsv `(list[float])`: the value of the rsv
        '''

        for i in range(13,len(self.list_of_date)):
            max_value = np.max(self.list_of_maximum_price[i-13:i+1]) ## finding the max values
            min_value = np.min(self.list_of_minimum_price[i-13:i+1]) ## finding the min values
            value = self.list_of_ending_price[i] ## getting the price of the day

            if (max_value-min_value) == 0: ## in case if something is wrong
                self.list_of_rsv= np.append(self.list_of_rsv,-10000000000)
            else:
                self.list_of_rsv= np.append(self.list_of_rsv,(value-min_value)/(max_value-min_value)*100) ## calculating the rsv value
        
        return self.list_of_rsv ## return the entire list
    
    def K(self):
        '''
        This is the function that we use to calculate the K value

        Parameters:self

        Returns:
        list_of_k_value `(list[float])`: the value of the k value
        '''
        for i in range(len(self.list_of_rsv)):
            self.k_value *=2/3  ## applying the forumla
            self.k_value += self.list_of_rsv[i]/3 ## continue to do so
            self.list_of_k_value=np.append(self.list_of_k_value,self.k_value) ## append the value to the list

    def D(self):
        r'''
        This is the function that we use to calculate the D value
        so the equationis is as follows:

        D_{i} = 2/3 * D_{i-1} + 1/3 * K_{i}

        Parameters(Inputs):
        ----------

        self

        Returns:
        ----------
        list_of_d_value `(list[float])`: the value of the d value
        '''
        for i in range(len(self.list_of_k_value)):
            self.d_value *=2/3 ## applying the forumla
            self.d_value += self.list_of_k_value[i]/3 ## continue to do so
            self.list_of_d_value=np.append(self.list_of_d_value,self.d_value) ## append the value to the list
        
        return self.list_of_d_value ## return the entire list
    
    def W(self):
        '''
        This is the function that we use to calculate the W value and return it as a list

        Equation:
        W_{i} = (MFI_{i}+RSI_{i}+D_{i+3})/3

        Parameters:
        -----------
        self (so like it is dependent on the list of MFI, RSI, and D value) cannot work without the previous function

        Returns:
        -----------
        W_list `(list[float])`: the value of the W value
        '''
        for i in range(len(self.list_of_ending_price)-14-self.a-14-14):
            W_value = (self.list_of_MFI[i]+self.rsi_list[i]+self.list_of_d_value[i+3])/3
            self.W_list = np.append(self.W_list,W_value)

        return self.W_list

    def W_moderate(self):
        '''
        This is the function that we use to calculate the W_moderate value and return it as a list

        Equations:

        W_sell = *1/2* * 0.618^{2} * min(MFI,RSI,D)+1/2 * max(MFI,RSI,D)+1/2*0.618 * median(MFI,RSI,D)

        W_moderate = *1/2* * 0.618^{2} * max(MFI,RSI,D)+1/2 * min(MFI,RSI,D)+1/2*0.618 * median(MFI,RSI,D)

        Parameters(Inputs):
        -----------
        * self

        Returns:
        -----------
        W_moderate_list `(list[float])`: the value of the W_moderate value as aa list
        '''
        W_moderate_list = np.array([]) ## initial value for W moderate list
        W_sell_list = np.array([]) ## initial value for W sell list
        for i in range(len(self.list_of_ending_price)-self.a):
            temp_array = np.array([]) ## initial value for temp_array, in fact we are just making a container for all three values
            temp_array = np.append(temp_array,self.list_of_MFI[i]) ## append the value of MFI
            temp_array = np.append(temp_array,self.rsi_list[i-2]) ## append the value of RSI
            temp_array = np.append(temp_array,self.list_of_d_value[i]) ## append the value of D
            W_moderate = 1/2*0.618**2*np.max(temp_array)+1/2*np.min(temp_array)+1/2*0.618*np.median(temp_array) ## calculate the W_moderate value
            W_sell = 1/2*0.618**2*np.min(temp_array)+1/2*np.max(temp_array)+1/2*0.618*np.median(temp_array) ## calculate the W_sell value

            W_moderate_list = np.append(W_moderate_list,W_moderate) ## append the value to the list
            W_sell_list = np.append(W_sell_list,W_sell) ## append the value to the list

            if W_moderate < 17:
                self.comparing_date_purchase = np.append(self.comparing_date_purchase,i+self.a) ## append the value to the list
                self.list_of_reflection = np.append(self.list_of_reflection,i) ## append the value to the list
            if W_sell >45:
                self.comparing_date_sell_off = np.append(self.comparing_date_sell_off,i+self.a) ## append the value to the list
        
        self.W_moderate_list_within_class = W_moderate_list ## return the entire list
        self.W_sell_list_within_class = W_sell_list ## return the entire list

        return W_moderate_list,W_sell_list ## return the entire list

    def calucate_elasped_days(self,start_date,end_date):
        '''
        This is the function that we use to calculate the elasped days

        Parameters(Inputs):
        -----------
        start_date `(str)`: the start date
        end_date `(str)`: the end date
        
        Returns:
        -----------
        elasped_days `(int)`: the elasped days
        '''
        date_format = "%Y-%m-%d"
        start_datetime = datetime.strptime(start_date,date_format) ## convert the given string to datetime and it should be the starting date
        end_datetime = datetime.strptime(end_date,date_format) ## convert the given string to datetime and it should be the ending date

        elasped_days = (end_datetime-start_datetime).days

        return elasped_days

    def removing_stuff_from_the_list(self,buy_list,sell_list):
        '''
        This is the function that we use to remove the duplicate values in the buy list and sell list

        Parameters(Inputs):
        -----------
            buy_list :
                `(list[float])`: the list of buy list
            sell_list :
                `(list[float])`: the list of sell list

        Returns:
        -----------
            removal_list_in_buy_list 
                `(list[float])`: the list of removal list in buy list
            removal_list_in_sell_list 
                `(list[float])`: the list of removal list in sell list
        '''
        removal_list_in_buy_list = np.array([]) ## initial value for removal list in buy list
        ## it is for removing the duplicate values in the buy list 
        removal_list_in_sell_list = np.array([]) ## initial value for removal list in sell list
        ## it is for removing the duplicate values in the sell list

        for j in range(len(sell_list)):
            if (j) > int(len(buy_list)):
                break
            else:
                if sell_list[j] == sell_list[j-1]:
                    if (buy_list[j]>buy_list[j-1]):
                        removal_list_in_buy_list = np.append(removal_list_in_buy_list,buy_list[j])
                        removal_list_in_sell_list = np.append(removal_list_in_sell_list,sell_list[j])

        for i in removal_list_in_buy_list:
            buy_list = np.delete(buy_list,np.where(buy_list==i))
        
        for j in removal_list_in_sell_list:
            sell_list = np.delete(sell_list,np.where(sell_list==j))
        
        return buy_list,sell_list
    
    def remove_duplicate_with_indices(self,buying_date,selling_date):
        '''
        This is the function that we use to remove the duplicate values in the buying date and selling date

        Parameters(Inputs):
        -----------
            buying_date :
                `(list[float])`: the list of buying date
            selling_date :
                `(list[float])`: the list of selling date

        Returns:
        -----------
            unique_list 
                `(list[float])`: the list of unique list
            unique_indices 
                `(list[float])`: the list of unique indices
            unique_indices_for_buying_list 
                `(list[float])`: the list of unique indices for buying list
        '''

        unique_list = np.array([]) ##uniuqe element in the list 
        unique_indices = np.array([]) ## unique indices in the list
        unique_indices_for_buying_list = np.array([]) ## unique indices for buying list
        seen = set() ## making a set for the seen values

        for index,item in enumerate(selling_date): ## loop through the selling date
            if item not in seen:
                unique_list = np.append(unique_list,item)
                unique_indices = np.append(unique_indices,index)
                unique_indices_for_buying_list = np.append(unique_indices_for_buying_list,buying_date[index])
                seen.add(item)
        
        return unique_list,unique_indices,unique_indices_for_buying_list
     
    def calucate_profit(self,buying_price,selling_price):
        '''
        This is the function that we use to calculate the profit

        Parameters(Inputs):
        -----------
        buying_price `(float)`: the buying price
        selling_price `(float)`: the selling price

        Returns:
        -----------
        profit `(float)`: the profit
        '''
        if self.area == "america":
            quantity = 10000000/(buying_price)
            quantity = round(quantity,0)
            # print(quantity)
            cost = quantity * buying_price*1.0028
            # print(cost)
            sell = quantity * selling_price
            # print(sell)
            difference = sell-cost
        else:
            quantity = 10000000/(buying_price)
            quantity = round(quantity,-2)
            # print(quantity)
            cost = quantity * buying_price*1.0028
            # print(cost)
            sell = quantity * selling_price
            # print(sell)
            difference = sell-cost
        
        return cost,difference


    def income(self):
        '''
        This is the function that we use to calculate the income

        -----------
        Parameters(Inputs):
        -----------
        * self: Just pass in the object

        -----------
        Returns:
        -----------
        * ag `(float)`: the ag value
        * agpd `(float)`: the agpd value
        * len(self.elasped_day) `(int)`: the length of the elasped day
        * average_day `(float)`: the average day
        * day_std_deviation `(float)`: the standard deviation of the day
        * revenue_per_year `(float)`: the revenue per year
        '''


        buying_date= np.array([]) ## initial value for buying date
        selling_date = np.array([]) ## initial value for selling date

        # print("comparing date purchase : ",self.comparing_date_purchase)
        # print("comparing date sell off : ",self.comparing_date_sell_off)

        for i in self.comparing_date_purchase: ## loop through the comparing date purchase
            self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.list_of_ending_price[int(i)]) ## append the value to the list
            for j in self.comparing_date_sell_off:
                if int(j)-int(i)>=0:
                    self.actual_actual_purchase = np.append(self.actual_actual_purchase,i) ## append the value to the list
                    self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_ending_price[int(j)])
                    buying_date = np.append(buying_date,self.list_of_date[int(i)]) ## append the date to the buying date list => When we buy and append it to the list
                    selling_date = np.append(selling_date,self.list_of_date[int(j)]) ## append the date to the selling date list => When we sell and append it to the list
                    break

        self.buy_at_ending_price,self.sell_at_ending_price= self.removing_stuff_from_the_list(self.buy_at_ending_price,self.sell_at_ending_price) ## remove the duplicate values in the list
        result_list_for_selling_dates,indices,unique_indices_for_buying_list = self.remove_duplicate_with_indices(buying_date,selling_date) ## remove the duplicate values in the list

        for i in range(len(unique_indices_for_buying_list)):
            self.elasped_day = np.append(self.elasped_day,self.calucate_elasped_days(unique_indices_for_buying_list[i],result_list_for_selling_dates[i])) ## append the days that have been passed to the list
        
        self.total_elasped_day=np.sum(self.elasped_day) ## sum the total elasped day

        if (len(self.elasped_day) == 0):
            average_day = 0
            day_std_deviation = 0
        else:
            average_day = np.mean(self.elasped_day) ## calculate the average day
            day_std_deviation = np.std(self.elasped_day) ## calculate the standard deviation of the day
        
        for i in range(len(self.sell_at_ending_price)):
            cost,difference = self.calucate_profit(self.buy_at_ending_price[i],self.sell_at_ending_price[i]) ## calculate the profit
            self.total_cost = np.append(self.total_cost,cost) ## append the cost to the list
            self.total_revenue = np.append(self.total_revenue,difference) ## append the revenue to the list
        
        self.total_cost_value+=np.sum(self.total_cost) ## sum the total cost
        self.total_revenue_value+=np.sum(self.total_revenue) ## sum the total revenue

        if self.total_cost_value ==0:
            ag = -10
        else:
            ag = self.total_revenue_value/self.total_cost_value ## calculate the ag value

        print("ag : ",ag)   
        if (len(self.elasped_day) == 0):
            agpd = -10
        else:
            agpd = self.total_elasped_day/len(self.elasped_day) ## calculate the agpd value
        agpd = ag/agpd
        print("agpd : ",agpd)
        revenue_per_year = (agpd+1)**(261)
        print("revenue per year : ",revenue_per_year)
        print("average day : ",average_day)
        return ag,agpd,len(self.elasped_day),average_day,day_std_deviation,revenue_per_year
    
    def days_has_been_below_17(self):
        '''
        This is the function that we use to calculate the days that has been below 17
        '''
        counter= 0
        for i in range(1,len(self.W_moderate_list_within_class)):
            if (self.W_moderate_list_within_class[-i])<=17:
                counter +=1
            else:
                break        
        return counter
    
    def re_work(self):
        '''
        This is the function that we use to reset the calucation and work on the prediction value
        '''
        self.get_date()
        self.RSV()
        self.rsi_list = self.ema()
        self.K()
        self.d_list = self.D()
        self.MFI_list = self.MFI_list1()
        # print(len(self.rsi_list))
        self.W_moderate_list,self.W_sell_list = self.W_moderate()
        # print(self.W_moderate_list_within_class)
        self.ag, self.agpd,self.number_of_trade,self.average_day, self.day_std_deviation,self.revenue_per_year = self.income()
        self.average_volume = np.mean(self.list_of_volume_of_exchange)    

    def close(self):
        '''
        This is the function that we use to close the object and resetting all the variable that we are using so that we can reinitate the object
        '''

        self.list_of_opening_price = np.array([]) ## initial value for list of opening price
        self.list_of_maximum_price = np.array([]) ## initial value for list of maximum price
        self.list_of_minimum_price = np.array([]) ## initial value for list of minimum price
        self.list_of_volume_of_exchange = np.array([]) ## initial value for list of volume of exchange
        self.alpha = 2/15 ## the mutiplier for ema values 
        self.ema_value = 30 ## initial value for ema
        self.price = 0 ## initial value for price
        self.date = 0 ## initial value for date
        self.date_14 = 0 ## initial value for date_14
        self.k_value = 50 ## initial value for k value
        self.list_of_date = np.array([]) ## initial value for list of date
        self.list_of_ending_price = np.array([]) ## initial value for list of ending price
        self.list_of_rsv = np.array([]) ## initial value for list of rsv
        self.list_of_k_value = np.array([]) ## initial value for list of k value
        self.list_of_d_value = np.array([]) ## initial value for list of d value
        self.d_value = 50 ## initial value for d value
        self.list_of_MFI = np.array([]) ## initial value for list of MFI
        self.sum_of_positive_ema_value = 0 
        self.sum_of_negative_ema_value = 0
        self.list_of_volume_exceed = np.array([]) ## initial value for list of volume exceed
        self.list_of_rate_of_change = np.array([]) ## initial value for list of volume
        self.list_after_editing = np.array([]) ## initial value for list after editing
        self.list_of_volume_of_exchange_hand = np.array([]) ## initial value for list of volume of exchange hand
        self.list_of_rate_of_change_in_float = np.array([]) ## initial value for list of rate of change in float
        self.up = np.array([]) ## initial value for up
        self.down = np.array([]) ## initial value for down
        self.ema_list = np.array([]) ## initial value for ema list
        self.ema_up = 0
        self.ema_down = 0
        self.rsi_list = np.array([]) ## initial value for rsi list
        self.W_list = np.array([]) ## initial value for W list
        self.W_value = 0
        self.a = 0 
        self.mfr = 0
        self.comparing_date_purchase = np.array([]) ## initial value for comparing date purchase
        self.comparing_date_sell_off = np.array([]) ## initial value for comparing date sell
        self.strings = np.array([]) ## initial value for strings
        self.x =0
        self.actual_purchase = np.array([]) ## initial value for actual purchase
        self.actual_sell_off = np.array([]) ## initial value for actual sell off
        self.removal = 0 
        self.actual_actual_purchase = np.array([]) ## initial value for actual actual purchase
        self.total_cost = np.array([]) ## initial value for total cost
        self.total_revenue =np.array([]) ## initial value for total revenue
        self.elasped_day = np.array([]) ## initial value for elasped day
        self.number_of_trade = 0
        self.total_cost_value= 0
        self.total_revenue_value =0
        self.total_elasped_day= 0 
        self.ag = 0
        self.agpd=0
        self.revenue_per_year = 0
        self.buy_at_ending_price = np.array([]) ## initial value for buy at ending price
        self.sell_at_ending_price =np.array([]) ## initial value for sell at ending price
        self.current_price =0 
        self.current_price_list = np.array([]) ## initial value for current price list
        self.list_of_reflection = np.array([]) ## initial value for list of reflection
        self.W_moderate_list = np.array([]) ## initial value for W moderate list
        self.W_sell_list = np.array([])
        self.W_moderate_list_within_class=np.array([]) ## initial value for W moderate list within class
        self.elasped_day_list = np.array([]) ## initial value for elasped day list
        self.W_sell_list_within_class = np.array([]) ## initial value for W sell list within class

if __name__ == "__main__":
    ## demo program for running the thing
    time1 = time.time_ns() ##recording the time
    a = risk_assessment_library("PLL") ## running the object and get the object
    print(a.number_of_trade)
    # a.close()
    time2 = time.time_ns() ## marking the running time
    # print("Time taken : ",time2-time1)
    print("in seconds:",(time2-time1)/1000000000) ## showcasing how fast can it run

    # for i in range(len(a.W_moderate_list_within_class)):
    #     print(a.W_moderate_list_within_class[i])

