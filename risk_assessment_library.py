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
    absolut_trade_winrate = 0
    draw_win_winrate = 0
    draw_lose_winrate = 0
    lose_winrate = 0 

    def __init__(self, name,area="",W_buy=17, W_sell=26,target_rate = 0.03, losing_rate = 0.03):
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
        self.stock_symbol = name ## identifier for the stock symbol
        self.W_buy = W_buy ## the W_buy value
        self.W_sell = W_sell ## the W_sell value
        self.target_rate = target_rate ## the target rate for the stock
        self.losing_rate = losing_rate ## the losing rate for the stock
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

        past_record = "generated_file/America/stock_data/{}.txt".format(self.name) ## the past record of the data
        if os.path.exists(past_record): ## if the past record exists and what if the record is empty tho? 
            self.getting_the_list_from_the_file(past_record)

            ## Check if the past record is up to date or not 
            import pandas as pd
            from pandas.tseries.holiday import USFederalHolidayCalendar
            from pandas.tseries.offsets import CustomBusinessDay
            US_BUSINESS_DAY = CustomBusinessDay(calendar=USFederalHolidayCalendar())
            # # print(US_BUSINESS_DAY)
            current_datetime = datetime.now() ## get the current datetime
            truth_last_day = current_datetime -timedelta(days=1)## get the last day of the business day
            print(truth_last_day)
            last_date = str(self.list_of_date[-1])
            print("Current date: ", current_datetime)
            print("Last date in the past record: ", last_date)


            if truth_last_day.strftime("%Y-%m-%d") != last_date :
                ## need to update
                print("The past record is not up to date, need to update the data and use the scrapper and should be able to call for the indivudal one")
                ## Just cat the pandas dataframe la 
                ## findig the index of the last date in the list of date
                index_of_last_date = np.where(self.list_of_date == last_date)[0][0] ## finding the index of the last date in the list of date
                ## getting the last date in the orginal database
                table_of_database = pd.read_table(stock_price_database,sep=",",lineterminator="\n",names=['Date','Close','High','Low','Open','Volume']) ## getting the last date in the orginal database
                ## finding the index of the so called last date in the current database 
                # print(table_of_database['Date'][:10])

                # print(table_of_database['Date'])

                ## need to split string first => for other stuff
                # self.split_string(stock_price_database) ## split the string first and getting all the data
                ## rerun the previous algorithm to get the data
                ## think of the number of iteration, may be better if i just use the index to help with the iteration 
                ## for example, just do something like 
                # for i in range(index_of_last_date+1,len(self.list_of_date)):
                ## but first we need to track down the last date's index 


                ## making the data in similar format to the table_of_database ## Assume the past data_doesn't exist  

                ## need to check with the data inside to see if it is up to date or not and calucate the resultant missing day or something
                ## I am thinking about calling the scrapper automatically 
            else:
                print("Can use the past record")

            # print("The past record exists, we can use it")

            for i in range(len(self.list_of_ending_price)-self.a):

                if self.W_moderate_list[i] < W_buy: ## if the W_moderate is less than W_buy
                    self.comparing_date_purchase = np.append(self.comparing_date_purchase,i+self.a) ## append the indices of the purchase date in the list of_date to comparing date purchase
                    self.list_of_reflection = np.append(self.list_of_reflection,i) ## append the value to the list
                if self.W_sell_list[i] > W_sell:
                    self.comparing_date_sell_off = np.append(self.comparing_date_sell_off,i+self.a) ## append the indices of the date that we ought to sell off to the comparing date sell off
                    # print("Sell off date: ",self.list_of_date[i+self.a]) ## print the sell off date
        
        else: ## if the past record does not exist
            
            if self.area == "industry": ## since we are using akshare => that is their ways of doing it
                num_of_data = self.split_string_for_industry(stock_price_database)
            else:
                num_of_data = self.split_string(stock_price_database)
                # print(self.list_of_date) ## print the first string to see if it is correct or not

            if num_of_data == 10: ## filter the stocks with not enough data
                self.agpd = -100
                raise Exception("Not enough data")
        
            self.get_date() ## getting the date 
            self.RSV()  ## getting the rsv list
            self.rsi_list = self.ema() ##  running through ema function to get the rsi function 
            self.K()  ## running the k forumla
            self.d_list = self.D() ## running the d forumla
            self.MFI_list = self.MFI_list1() ## running MFI list as well
            self.W_moderate_list,self.W_sell_list = self.W_moderate(W_buy,W_sell) ## combining and running thr W moderate forumla 
            # print(self.W_moderate_list_within_class)

        self.ag, self.agpd,self.number_of_trade,self.average_day, self.day_std_deviation,self.revenue_per_year,self.absolut_trade_winrate,self.draw_win_winrate,self.draw_lose_winrate,self.lose_winrate = self.income() ## doing the final analysis and testing it through the past data by adding the virtual money and see
        self.average_volume = np.mean(self.list_of_volume_of_exchange)*self.list_of_ending_price[-1]  ## calucating the average of all
        # self.close()

    def processing_data(self,filename):
        f=open(filename,'r',encoding="utf8") ### opening the files 
        self.strings = f.read().split("\n") ## reading the individual content of the file
        self.strings = self.strings[:-1] ## remove the last white space => sometimes it will hinder the understanding
        
        if self.area == "industry": ## since we are using akshare => that is their ways of doing it
            num_of_data = self.split_string_for_industry()
        else:
            num_of_data = self.split_string()
            # print(self.list_of_date) ## print the first string to see if it is correct or not

        if num_of_data == 10: ## filter the stocks with not enough data
            self.agpd = -100
            raise Exception("Not enough data")
    
        self.get_date() ## getting the date 
        self.RSV()  ## getting the rsv list
        self.rsi_list = self.ema() ##  running through ema function to get the rsi function 
        self.K()  ## running the k forumla
        self.d_list = self.D() ## running the d forumla
        self.MFI_list = self.MFI_list1() ## running MFI list as well
        self.W_moderate_list,self.W_sell_list = self.W_moderate(self.W_buy,self.W_sell) ## combining and running thr W moderate forumla 
        # print(self.W_moderate_list_within_class)

    def getting_the_list_from_the_file(self,filename):
        '''
        This is the function that we use to get the list from the file

        -----------
        Parameters(Inputs):
        -----------
        * filename `(str)`: the name of the file that we want to read

        -----------
        Returns:
        -----------
        nothing but prepre all the list
        '''

        with open(filename, 'r', encoding='utf8') as f:  ## open the file
            strings = f.read().split("\n")  ## read the file and split by new line

            strings = strings[1:-2]  ## remove the first and the last element
            for string in strings:
                string= string.split(",",12)
                
                ### append the value to the list
                self.list_of_date = np.append(self.list_of_date,string[0])
                self.list_of_opening_price = np.append(self.list_of_opening_price,float(string[1]))
                self.list_of_ending_price = np.append(self.list_of_ending_price,float(string[2]))
                self.list_of_maximum_price = np.append(self.list_of_maximum_price,float(string[3]))
                self.list_of_minimum_price = np.append(self.list_of_minimum_price,float(string[4]))
                self.list_of_volume_of_exchange = np.append(self.list_of_volume_of_exchange,float(string[5]))
                self.list_of_MFI = np.append(self.list_of_MFI,float(string[6]))
                self.rsi_list = np.append(self.rsi_list,float(string[7]))
                self.list_of_k_value = np.append(self.list_of_k_value,float(string[8]))
                self.list_of_d_value = np.append(self.list_of_d_value,float(string[9]))
                self.W_moderate_list = np.append(self.W_moderate_list,float(string[10]))
                self.W_sell_list = np.append(self.W_sell_list,float(string[11]))
    
    def split_string(self,stock_price_database):
        '''
        This is the function that we use to split the string
        No need for the input or output
        '''
        f=open(stock_price_database,'r',encoding="utf8") ### opening the files 
        self.strings = f.read().split("\n") ## reading the individual content of the file
        self.strings = self.strings[:-1] ## remove the last white space => sometimes it will hinder the understanding
        
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
        
    def split_string_for_industry(self,stock_price_database):
        '''
        This is the function that we use to split the string
        No need for the input or output
        It is spectifically for the indistry
        '''
        f=open(stock_price_database,'r',encoding="utf8") ### opening the files 
        self.strings = f.read().split("\n") ## reading the individual content of the file
        self.strings = self.strings[:-1] ## remove the last white space => sometimes it will hinder the understanding
        

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
                # print("typical price : ",typical_price)
                raw_money = typical_price*self.list_of_volume_of_exchange[i+self.x-13]
                money_positve_flow = np.append(money_positve_flow,raw_money)
                # print("money positive flow : ",money_positve_flow)
            else:
                typical_price = (max_value+min_value+self.list_of_ending_price[i+self.x-13])/3
                raw_money = typical_price*self.list_of_volume_of_exchange[i+self.x-13]
                money_negative_flow = np.append(money_negative_flow,raw_money)
                # print("money negative flow : ",money_negative_flow)

        total_postive_flow = np.sum(money_positve_flow)
        total_negative_flow = np.sum(money_negative_flow)

        if total_negative_flow == 0:
            mfr = 1000000000000
        else:
            mfr = total_postive_flow/total_negative_flow
            # print(mfr)

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

    def W_moderate(self, W_buy_trade, W_sell_trade): 
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

            if W_moderate < W_buy_trade: ## if the W_moderate is less than W_buy
                self.comparing_date_purchase = np.append(self.comparing_date_purchase,i+self.a) ## append the indices of the purchase date to comparing date purchase
                self.list_of_reflection = np.append(self.list_of_reflection,i) ## append the value to the list
            if W_sell > W_sell_trade:
                self.comparing_date_sell_off = np.append(self.comparing_date_sell_off,i+self.a) ## append the indices of the date that we ought to sell off to the comparing date sell off
        
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


    def income(self,target_rate = 0.03, losing_rate = 0.03):
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

        win_trade = 0
        trade_count = 0
        absolute_win_trade_count = 0 ## trade that is win for more than 3%
        draw_win_trade_count = 0 ## trade that acheive when W_sell >= 26 and get some money afterward
        draw_lost_trade_count = 0 ## trade that acheive when W_sell >= 26 and lose some money afterward
        lose_trade_count = 0 ## trade that is lose for more than 3%
        draw_trade_count = 0 ## trade that acheived when W_sell >= 26
        draw_trade_start_day = np.array([]) ## the day that we start the draw trade

        past_record = 0 ## just an indicator variable so that we just don't keep on buying and we can have a like a gap

        ## rewrite version: 

        date_purchase = len(self.comparing_date_purchase)
        date_sell_off = len(self.comparing_date_sell_off)
        mid_way_sell_failture = False # indicator variable to prevent if more than two items exceed <3% and need to sell at the same time 
        ### like on 28 we sell the item <3% and yet  or it is caused by other issues

        i =0 ## pointer value for the purchase date and prepare for any increment of the value of the date_purchase
        buy_in_array_pointer = 0 ## Pointer value for buy_at_the end array

        # for i in range(len(self.comparing_date_purchase)):
        #     print("buying date: ",self.list_of_date[int(self.comparing_date_purchase[i])]) ## print the buying date
        # for i in range(len(self.comparing_date_sell_off)):
            # print("selling date: ",self.list_of_date[int(self.comparing_date_sell_off[i])]) 

        pointer_variable = 0 ## pointer variable for the comparing date sell off
        ### Pre-calibration: So more like what if date_sell_of < date_purchase for every single element
        ## Sound more like a bug, but it is not a bug, it is just the way that we are doing it
        ## there is more opporunity to sell off rather than buying it and it exist before we can buy it for the first time
        # pointer_variable = 0 ## pointer variable for the comparing date sell off
        for b in range(len(self.comparing_date_sell_off)):
            if self.comparing_date_sell_off[b]> self.comparing_date_purchase[0]:
                pointer_variable = b
                break
                print("Pointer variable: ",pointer_variable) ## print the pointer variable

        if pointer_variable > 0: ## if the pointer variable is greater than 0, then we can just set the date_sell_off to the pointer variable
            self.comparing_date_sell_off = self.comparing_date_sell_off[pointer_variable:] ## set the comparing date sell off to the pointer variable
        

        # for k in range(10):
        #     print("Comparing date purchase: ",self.comparing_date_purchase[k]) ## print the comparing date purchase
        #     print("Comparing date sell off: ",self.comparing_date_sell_off[k]) ## print the comparing date sell off
                    
        # print("Length of the comparing date purchase: ",len(self.comparing_date_purchase)) ## print the length of the comparing date purchase
        # print("Length of the comparing date sell off: ",len(self.comparing_date_sell_off)) ## print the length of the comparing date sell off

        while i< date_purchase: ##  Looping through the possible purchase date
            
            lost_very_early = False
            # if self.list_of_date[int(self.comparing_date_purchase[int(i)])] == "2022-10-17": ## if the date is 2023-10-27, then we just skip it
            #     print("Here")
            #     print(self.list_of_date[int(self.comparing_date_purchase[int(i)])])
            #     print(self.comparing_date_purchase[int(i)]) ## print the comparing date purchase
            # if lost_very_early:
            ###  Need to check if it drops for more than 3% yesterday 
            ###  More like the price difference between really and it violate the past record law, that is the issue

            if (self.buy_at_ending_price.any()> 0 and self.comparing_date_purchase.any() > 0 and self.list_of_minimum_price.any() > 0 ) and (self.list_of_minimum_price[int(self.comparing_date_purchase[(int(i))]) < self.buy_at_ending_price[buy_in_array_pointer]*(1-losing_rate)]): ## if the minimum price is less than the ending price*0.97
                # print("It dropped more than expected, we need to re-purchase it and re-set the buying price")
                self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]) ## append the value to the list
                buying_date = np.append(buying_date,self.list_of_date[int(self.comparing_date_purchase[int(i)])+1]) ## append the date to the buying date list => When we buy and append it to the list
                past_record = int(self.comparing_date_purchase[int(i)]) ## update the past record to the current purchase date
                # print("Dropper")

            # print("Past record: ",past_record) ## print the past record
            # print("Comparing date purchase: ",self.comparing_date_purchase[int(i)]) ## print the comparing date purchase
            ###  Need to check if we buy form yesterday 
            if ((i >0) and (past_record == int(self.comparing_date_purchase[int(i)])) and (len(buying_date)==len(selling_date))): ## if the past record is the same as the current purchase date and the buying price is the same as the opening price
                i+=1 ## increment the pointer value for the purchase date
                # print("Passing record")
                # print(self.list_of_date[int(self.comparing_date_purchase[int(i)])])
                continue ## continue to the next iteration of the loop

            # if self.comparing_date_purchase[int(i)]  == 583:
            #     print("Arrived")
            if i == len(self.comparing_date_purchase)-1: ## if we are at the last date of the purchase date
                print("We are at the last date of the purchase date, we need to sell it off")
                break

            ### If not, we can then assume that we can select when to sell 
            if i == 0 or len(buying_date) == len(selling_date): ## we are making a unique trade that jump out of the old cluster (or consecutive buying day)) 
                ## append the first element, meaning that we should probably
                self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.list_of_opening_price[int(self.comparing_date_purchase[int(i)])+1]) ## append the value to the list
                
                ### Past record is keep tracking on the pointer/number of element in the list_of_date that we just buy
                past_record = int(self.comparing_date_purchase[int(i)]+1) ## update the past record 

                ## keeping track of the date that we have made purhcases and stored it as list
                buying_date = np.append(buying_date,self.list_of_date[int(self.comparing_date_purchase[int(i)])+1]) ## append the date to the buying date list => When we buy and append it to the list

                # buy_in_array_pointer +=1 ## increment the pointer value for the buy in array pointer
            # if self.comparing_date_purchase[int(i)]  == 583:
            #     print("Arrived2")
            # if self.list_of_date[int(self.comparing_date_purchase[int(i)])] == "2022-10-17": ## if the date is 2023-10-27, then we just skip it
            #     print("Here")
            #     print(self.comparing_date_purchase[int(i)]) ## print the comparing date purchase
            if lost_very_early:
                j = i -1
            else:
                j = i ## Pointer value for looping through the sell off date
            # j=0
            while j < date_sell_off:
                ### looping through between the date between the buying date and the date that achieves 26
                # print("Comparing date purchase: ",self.comparing_date_purchase[int(i)]) ## print the comparing date purchase
                # print("Comparing date sell off: ",self.comparing_date_sell_off[int(j)]) ## print the comparing date sell off
                # if j == 891:
                #     print(self.buy_at_ending_price) ## print the buy at ending price
                #     print(buying_date) ## print the buying date
                #     print(selling_date) ## print the selling date
                # print(len(self.comparing_date_sell_off))
                # print("Comparing date purchase: ",self.comparing_date_purchase) ## print the comparing date purchase
                # print("Comparing date sell off: ",self.comparing_date_sell_off) ## print the comparing date sell off
                

                if j >= len(self.comparing_date_sell_off)-1: ## if the selling date is the last date in the list
                    # print("We are at the last date, we need to sell it off")
                    # print("Comparing date sell off: ",self.comparing_date_sell_off[int(j-1)])
                    # print(len(self.list_of_date))
                    # print(self.list_of_date[int(self.comparing_date_sell_off[int(j-1)])+1])
                    selling_date = np.append(selling_date,self.list_of_date[int(self.comparing_date_sell_off[int(j-1)])]) ## append the date to the selling date list => When we sell and append it to the list
                    break


                if int(self.comparing_date_sell_off[int(j)]+1) - int(self.comparing_date_purchase[int(i)]+1)>=0:
                    # if self.comparing_date_purchase[int(i)]   == 583:
                        # print("Finding option",self.comparing_date_sell_off[int(j)])
                    win_early = False ## indicator variable to check if we are win early or not 
                    drop_too_much = False ## indicator variable to check if we drop too much or not

                    ### Supposing the self.comparing_date_purchase store all the pointer of the list of dates that have W_buy value < 17
                    ### Supposing the self.comparing_date_sell_off store all the pointer of the list of dates that have W_sell value >= 26 
                    for k in range(int(self.comparing_date_purchase[int(i)])+1,int(self.comparing_date_sell_off[int(j)])+1): 
                        
                        ### if one of the day exceed 3%, we mark it as sell off date
                        if (self.list_of_maximum_price[k]> self.buy_at_ending_price[buy_in_array_pointer]*(1+target_rate)): ## if the maximum price is greater than the ending price*1.03
                            self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*(1+target_rate)) ## append the value to the list
                            selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
                            # print(self.list_of_date[int(k)]) ## print the date that we are selling
                            # print("Price that we are selling", self.buy_at_ending_price[buy_in_array_pointer]*1.03) ## print the price that we are selling
                            absolute_win_trade_count += 1 ## increment the absolute win trade count > 1.03 percentage
                            win_early = True ## set the win early to true
                            
                            break ## break the loop since we have found the win early point
                            
                            ### if the minimum price drop too much to a certain point, we need to cut off and we re-purchase it
                            ### If one of the day drop for more than 3%, we need to re-purhcase and re-sell it off 
                        elif (self.list_of_minimum_price[k] <= self.buy_at_ending_price[buy_in_array_pointer]*(1-losing_rate)):
                            ### for the selling price, we just need to append the newly added value there
                            self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*(1-losing_rate)) 
                            
                            selling_date = np.append(selling_date,self.list_of_date[int(k)]) 
                            ## append the date to the selling date list => When we sell and append it to the list

                            lose_trade_count += 1 ## increment the lose trade count < 0.97 percentage

                            ## we need to buy at the same day 
                            buying_date = np.append(buying_date,self.list_of_date[int(k)]) 
                            ## append the date to the buying date list => When we buy and append it to the list

                            self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*(1-losing_rate)) ## append the value to the list
                            ## append the value to the list

                            # print("Rmb today is the dat that we shitted: ",self.list_of_date[int(k)]) ## print the date that we are buying

                            ## if the i+1 exceeds the length of the comparing date purchase
                            if i+1 > len(self.comparing_date_purchase): 
                                self.comparing_date_purchase = np.append(self.comparing_date_purchase,int(k)) ## append the value to the list
                            else:
                                self.comparing_date_purchase = np.insert(self.comparing_date_purchase,i+1,int(k)) ## append the value to the list
                            ### No need to change the comparing_date_sell_off since it should be same day that we are selling it off if it reaches 26 

                            drop_too_much = True ## set the drop too much to true

                            lost_very_early = True

                            ## Past record is updated to k 
                            past_record = int(k) ## update the past record to the current k value

                            # i-=1

                            break ## break the loop since we have found the drop too much point
                    
                    ## if we didn't sell early / wait until W_sell >= 26
                    if drop_too_much == False and win_early == False: 
                        ## append the final ending price to the list
                        self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_ending_price[int(self.comparing_date_sell_off[int(j)]+1)])

                        ## record it to the selling date list
                        selling_date = np.append(selling_date,self.list_of_date[int(self.comparing_date_sell_off[int(j)]+1)]) ## append the date to the selling date list => When we sell and append it to the list
                        draw_trade_count += 1 ## increment the draw trade count
                        draw_trade_start_day = np.append(draw_trade_start_day,self.list_of_date[int(self.comparing_date_purchase[int(i)]+1)]) ## append the date to the draw trade start day list

                        break 
                    elif drop_too_much or win_early:
                        break

                j+=1 ## increment the pointer variable for the sell off date
            
            i+=1
            buy_in_array_pointer =-1 ## increment the pointer value for the buy in array pointer


        # while i < date_purchase: ## loop through the comparing date purchase
        #     # print("Which one are we are going to execute rn: ",self.list_of_date[int(self.comparing_date_purchase[int(i)])+1]) ## print the date that we are going to execute
        #     # if self.list_of_minimum_price[int(self.comparing_date_purchase[int(i)])] <= self.list_of_opening_price[int(self.comparing_date_purchase[int(i)])]*0.97: ## if the minimum price is less than the opening price*0.97
        #     #     print("We need to sell of early and not passing the past record")
        #     #     past_record = 0
        #     ## if the next day drop more than 3% and it is following the past recorrd => we need to overwrite that 
        #     # print("The past record is: ",past_record+1) ## print the past record
        #     # print("The comparing date purchase is: ",self.comparing_date_purchase[int(i)]) ## print the comparing date purchase
        #     if i > len(self.buy_at_ending_price):
        #         buy_in_array_pointer = -1 ## if the buy in array pointer exceeds the length of the buy at ending price, then we just set it to the last element

        #     if len(self.buy_at_ending_price) == len(self.sell_at_ending_price):
        #         if int(self.comparing_date_purchase[int(i)]+1) == len(self.list_of_opening_price) or int(self.comparing_date_purchase[int(i)]) == past_record+1:
        #             i+=1 ## increment the  pointer value for the purchase date
        #             # print("Has to pause for a bit")
        #             continue
        #         self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.list_of_opening_price[int(self.comparing_date_purchase[int(i)])+1]) ## append the value to the list
        #         buying_date = np.append(buying_date,self.list_of_date[int(self.comparing_date_purchase[int(i)]+1)]) ## append the date to the buying date list => When we buy and append it to the list

        #         # print("The price that we are buying", self.list_of_opening_price[int(self.comparing_date_purchase[int(i)]+1)])
        #         # print("After appending to the buy list", self.buy_at_ending_price)            # print("the date that we are going to buy is:", self.comparing_date_purchase[int(i)])
        #         past_record = int(self.comparing_date_purchase[int(i)])
        #     j = 0 ## pointer value for the sell off date    
        #     while j < date_sell_off:
        #         if self.comparing_date_sell_off[int(j)] - self.comparing_date_purchase[int(i)]>=0:
        #             self.actual_actual_purchase = np.append(self.actual_actual_purchase,self.comparing_date_purchase[int(i)]) ## append the value to the list
        #             sell_early = False
        #             drop_too_much = False
        #             # print("We are tracking on the price: ", self.buy_at_ending_price[buy_in_array_pointer])
        #             for k in range(int(self.comparing_date_purchase[(int(i))]+1),int(self.comparing_date_sell_off[(int(j))]+1)):
        #                 if self.list_of_maximum_price[k] >= self.buy_at_ending_price[buy_in_array_pointer]*1.03: ## if the maximum price is greater than the ending price*1.03
        #                     self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*1.03) ## append the value to the list
        #                     sell_early = True
        #                     # print("The sell early: ",self.buy_at_ending_price[buy_in_array_pointer]*1.03 )
        #                     selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
        #                     absolute_win_trade_count += 1 ## increment the absolute win trade count
        #                     break
        #                 elif self.list_of_minimum_price[k] <= self.buy_at_ending_price[buy_in_array_pointer]*0.97:
        #                     # print("This drop off early: ",self.list_of_opening_price[int(self.comparing_date_purchase[int(i)]+1)]*0.95 )
        #                     # print("The minimum price is: ",self.list_of_minimum_price[k])
        #                     # print("The comparing date purchase is: ",self.comparing_date_purchase)

        #                     # print("This drop off early: We shitted",self.buy_at_ending_price[buy_in_array_pointer]*0.97 )

        #                     self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*0.97)
        #                     drop_too_much = True
        #                     selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
        #                     lose_trade_count += 1 ## increment the lose trade count
        #                     # print("This drop off early: ",self.list_of_opening_price[int(self.comparing_date_purchase[int(i)]+1)]*0.95)
        #                     ## the hot added feature 
        #                     ## when broke and then we re - purchase again 
        #                     # print("Trigger here")
        #                     # print("the date that we are going to buy is: ",self.list_of_date[int(self.comparing_date_purchase[int(i)])])

        #                     # print("The k value is: ",k)

        #                     if self.comparing_date_purchase[(int(i))]+1 == k:
        #                         past_record = 0 ## reset the past record to something weird to avoid error
        #                         j+=1 ## increment the pointer value for the buy in date
        #                         # print("Remove past record and continue")
        #                         break ## if the date that we are buying date that we append is the same as the next day, then we just remove the past record and continue

        #                     if i+1 >= len(self.comparing_date_purchase): ## idfk trying to append if it exceeds the i+1
        #                         self.comparing_date_purchase = np.append(self.comparing_date_purchase,int(k)) ## append the value to the list
        #                     else:
        #                         self.comparing_date_purchase = np.insert(self.comparing_date_purchase,i+1,int(k)) ## append the value to the list
        #                     self.list_of_reflection = np.append(self.list_of_reflection,int(k)) ## append the value to the list # can not care for now
        #                     if i+1 >= len(self.buy_at_ending_price):
        #                         self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*0.97)
        #                     else:
        #                         self.buy_at_ending_price = np.insert(self.buy_at_ending_price,i+1,self.buy_at_ending_price[buy_in_array_pointer]*0.97) ## append the value to the list
                            
        #                     # print("We are going to buy on this date",self.list_of_date[int(k)]) ## print the date that we are going to buy
        #                     buying_date = np.append(buying_date,self.list_of_date[int(k)]) ## append the date to the buying date list => When we buy and append it to the list
        #                     # date_purchase += 1 ## update the date purchase
        #                     past_record = int(k)-1 ## update the past record
        #                     # print("Updated past record to: ",self.list_of_date[int(past_record)]) ## print the past record

        #                     # print("The past record is updated to: ",past_record)
        #                     # print("The comparing date purchase is updated to: ",self.comparing_date_purchase)
        #                     # print("The buying price is updated to: ",self.buy_at_ending_price)
        #                     # print("The buying date is updated to: ",buying_date)
        #                     break

        #             if not sell_early and not drop_too_much: ## if we didn't sell early / wait until W_sell >= 26
        #                 self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_ending_price[int(self.comparing_date_sell_off[int(j)])])
        #                 selling_date = np.append(selling_date,self.list_of_date[int(self.comparing_date_sell_off[int(j)])]) ## append the date to the selling date list => When we sell and append it to the list  
        #                 draw_trade_count += 1 ## increment the draw trade count
        #                 draw_trade_start_day = np.append(draw_trade_start_day,self.list_of_date[int(self.comparing_date_purchase[int(i)])]) ## append the date to the draw trade start day list                  

        #             # buying_date = np.append(buying_date,self.list_of_date[int(self.comparing_date_purchase[int(i)]+1)]) ## append the date to the buying date list => When we buy and append it to the list
        #             break
        #         j+=1 ## increment the pointer value for the sell off date
        #     i+=1 ## increment the pointer value for the purchase date

        # print("sell at ending price: ", self.sell_at_ending_price)
        # print("selling date: ", selling_date)
        # print("Buy at ending price: ",self.buy_at_ending_price)

        # for i in self.comparing_date_purchase: ## loop through the comparing date purchase
        #     if i+1 == len(self.list_of_opening_price) or i-1 == past_record:
        #         continue
        #     self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.list_of_opening_price[int(i+1)]) ## append the value to the list
        #     past_record = i
        #     for j in self.comparing_date_sell_off:
        #         if int(j)-int(i)>=0:
        #             self.actual_actual_purchase = np.append(self.actual_actual_purchase,i) ## append the value to the list
        #             sell_early = False
        #             drop_too_much = False
        #             for k in range(int(i+1),int(j+1)): ## loop through the range of i to j
        #                 if self.list_of_maximum_price[k] >= self.list_of_opening_price[int(i+1)]*1.03: ## if the maximum price is greater than the ending price*1.03
        #                     ### try out for opening price and orginal idea is ending_price
        #                     # print("The sell early: ",self.list_of_opening_price[int(i+1)]*1.03)

        #                     self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_opening_price[int(i+1)]*1.03) ## append the value to the list
        #                     sell_early = True
        #                     selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
        #                     break

        #                 if self.list_of_minimum_price[k] <= self.list_of_opening_price[int(i+1)]*0.95:
        #                     # print("This drop off early: ",self.list_of_opening_price[int(i+1)]*0.95 )
        #                     self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_opening_price[int(i+1)]*0.95)
        #                     drop_too_much = True
        #                     selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
        #                     break

        #                 ## need to figure out a way loop hot added date in the failture one
                    
        #             if not sell_early and not drop_too_much: ## if we didn't sell early / wait until W_sell >= 26
        #                 self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_ending_price[int(j)])
        #                 selling_date = np.append(selling_date,self.list_of_date[int(j)]) ## append the date to the selling date list => When we sell and append it to the list

        #             buying_date = np.append(buying_date,self.list_of_date[int(i)]) ## append the date to the buying date list => When we buy and append it to the list
        #             break

        # print("sell at ending price: ", self.sell_at_ending_price)
        # print("selling date: ", selling_date)
        # print("Buy at ending price: ",self.buy_at_ending_price)
        ### Gonna remove some buying requirement 
        #
        #  
        ####

        # self.buy_at_ending_price = np.unique(self.buy_at_ending_price) ## remove the duplicate values in the list
        # self.sell_at_ending_price = np.unique(self.sell_at_ending_price) ## remove the duplicate values in the list
        # print("buying price : ",self.buy_at_ending_price)
        # print("selling price : ",self.sell_at_ending_price)
        # print("One to one corrspondence between buying and selling date: ", len(buying_date) == len(selling_date)) ## check if the length of the buying date and selling date are the same
        # for i in range(len(buying_date)):
            # print("buying date : ",buying_date[i]) ## print the buying date

        # for i in range(len(selling_date)):
            # print("selling date : ",selling_date[i])

        # self.buy_at_ending_price,self.sell_at_ending_price= self.removing_stuff_from_the_list(self.buy_at_ending_price,self.sell_at_ending_price) ## remove the duplicate values in the list
        # result_list_for_selling_dates,indices,unique_indices_for_buying_list = self.remove_duplicate_with_indices(buying_date,selling_date) ## remove the duplicate values in the list
        
        # print("result list for buying price : ",self.buy_at_ending_price) ## print the result list for selling dates
        # print("result list for selling price : ",self.sell_at_ending_price) ## print the result list for buying dates
        # print("One to one corrspondence between buying and selling date: ", len(self.buy_at_ending_price) == len(self.sell_at_ending_price)) ## check if the length of the buying date and selling date are the same

        # print("Number of trades : ",len(self.buy_at_ending_price)) ## print the number of trades
        # print("Number of sell_of: ",len(self.sell_at_ending_price)) ## print the number of buy in

        # print("buying date : ",buying_date) ## print the buying date
        # print("selling date : ",selling_date) ## print the selling date

        # for i in range(len(self.buy_at_ending_price)):
        for i in range(len(buying_date)):
            # print("day", self.elasped_day) ## print the elasped day
            # print("buying date : ",buying_date[i]) ## print the buying date
            # print("selling date : ",selling_date[i]) ## print the selling date
            self.elasped_day = np.append(self.elasped_day,self.calucate_elasped_days(buying_date[i],selling_date[i])) ## append the days that have been passed to the list
            # print("elasped day : ",self.calucate_elasped_days(buying_date[i],selling_date[i])) ## print the elasped day

        # for i in range(len(unique_indices_for_buying_list)):
        #     self.elasped_day = np.append(self.elasped_day,self.calucate_elasped_days(unique_indices_for_buying_list[i],result_list_for_selling_dates[i])) ## append the days that have been passed to the list
        
        self.total_elasped_day=np.sum(self.elasped_day) ## sum the total elasped day
        ## After summing it, it tend to infinite
        if self.total_elasped_day == 0: ## if the total elasped day is 0, then we just set it to 1
            self.total_elasped_day = len(self.elasped_day) ## set the total elasped day to the length of the elasped day

        if (len(self.elasped_day) == 0):
            average_day = 0
            day_std_deviation = 0
        else:
            average_day = np.mean(self.elasped_day) ## calculate the average day
            day_std_deviation = np.std(self.elasped_day) ## calculate the standard deviation of the day
        
        # print("Buying Price",self.buy_at_ending_price) ## print the buying price
        # print("Buying Date",buying_date) ## print the buying date
        # print("Selling Price",self.sell_at_ending_price)
        # print("Selling Date",selling_date) ## print the selling date
        # np.set_printoptions(threshold=np.inf)
        # print(self.comparing_date_sell_off)

        for i in range(len(self.sell_at_ending_price)):
            cost,difference = self.calucate_profit(self.buy_at_ending_price[i],self.sell_at_ending_price[i]) ## calculate the profit
            self.total_cost = np.append(self.total_cost,cost) ## append the cost to the list
            self.total_revenue = np.append(self.total_revenue,difference) ## append the revenue to the list
            if (difference > 0):
                win_trade+=1
                if buying_date[i] in draw_trade_start_day: ## if the buying date is in the draw trade start day
                    draw_win_trade_count += 1 ## increment the draw win trade count
            else:
                if buying_date[i] in draw_trade_start_day:
                    draw_lost_trade_count += 1 ## increment the draw lost trade count
            
            
            trade_count+=1


        # print("total cost : ",self.total_cost) ## print the total cost
        # print("total revenue : ",self.total_revenue)
        
        self.total_cost_value+=np.sum(self.total_cost) ## sum the total cost
        self.total_revenue_value+=np.sum(self.total_revenue) ## sum the total revenue

        # print("total cost value : ",self.total_cost_value) ## print the total cost value
        # print("total revenue value : ",self.total_revenue_value) ## print the total revenue value

        if self.total_cost_value ==0:
            ag = -10
        else:
            ag = self.total_revenue_value/self.total_cost_value ## calculate the ag value

        # print("ag : ",ag)   
        if (len(self.elasped_day) == 0):
            agpd = -10
        else:
            agpd = self.total_elasped_day/len(self.elasped_day) ## calculate the agpd value
        agpd = ag/agpd
        # print("agpd : ",agpd)
        revenue_per_year = (agpd+1)**(261)
        # print("revenue per year : ",revenue_per_year)
        # print("average day : ",average_day)
        self.win_rate = win_trade/trade_count if trade_count > 0 else 0
        absolute_win_trade_rate = absolute_win_trade_count/trade_count if trade_count > 0 else 0
        draw_win_trade_rate = draw_win_trade_count/trade_count if trade_count > 0 else 0
        draw_lose_trade_rate = draw_lost_trade_count/trade_count if trade_count > 0 else 0
        lose_trade_rate = lose_trade_count/trade_count if trade_count > 0 else 0
        # print("win rate : ",self.win_rate)
        # print("Number of trades : ",len(self.elasped_day))
        self.average_day = average_day
        return ag,agpd,len(self.elasped_day),average_day,day_std_deviation,revenue_per_year,absolute_win_trade_rate,draw_win_trade_rate,draw_lose_trade_rate,lose_trade_rate
    
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
        self.winrate = 0 ## initial value for winrate
        self.average_day = 0 ## initial value for average day
        self.absolut_trade_winrate = 0
        self.draw_win_winrate = 0
        self.draw_lose_winrate = 0
        self.lose_winrate = 0 
        
    def print_info(self):
        print(f"Stock Symbol: {self.stock_symbol}")
        print(f"AGPD: {self.agpd}")
        print(f"Number of Trades: {self.number_of_trade}")
        print(f"Ending Price: {self.list_of_ending_price[-1]}")
        print(f"W Moderate List: {self.W_moderate_list}")

if __name__ == "__main__":
    ## demo program for running the thing
    time1 = time.time_ns() ##recording the time
    a = risk_assessment_library("CPRT",W_buy=17,W_sell=26,target_rate=0.04,losing_rate=0.04) ## running the object and get the object
    a.print_info() ## print the information of the object
    # print(a.number_of_trade)
    # print(a.W_moderate_list_within_class[-1]) ## printing the W moderate list within class
    # print(a.d_list)
    # for i in range(10):
    #     print("rsi",a.list_of_rsv[i])
        
    #     print("d_value,",a.list_of_d_value[i])
    #     print("MFI:",a.MFI_list[i])
    # a.close()
    time2 = time.time_ns() ## marking the running time
    # print("Time taken : ",time2-time1)
    print("in seconds:",(time2-time1)/1000000000) ## showcasing how fast can it run

    # for i in range(len(a.W_moderate_list_within_class)):
    #     print(a.W_moderate_list_within_class[i])

