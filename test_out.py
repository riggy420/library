from numpy import doc
from psutil.tests import kernel_version
from risk_assessment_library import risk_assessment_library
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
from pathlib import Path

class try_out(risk_assessment_library):
    def __init__(self, stock_symbol,area="",W_buy=17, W_sell=26):
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

        # try:
        #     Path()

        ## retrieve the past record of the data to reduce time: 
        
    
        self.close() ### clearing the file first => Idk why can have error if you are spamming it for too long time
        self.name=stock_symbol ## idetnifier for the object
        self.stock_symbol = stock_symbol ## identifier for the stock symbol
        self.W_buy = W_buy ## the W_buy value
        self.W_sell = W_sell ## the W_sell value
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
        
        else: ## if the past record does not exist
            
            f=open(stock_price_database,'r',encoding="utf8") ### opening the files 
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
            self.W_moderate_list,self.W_sell_list = self.W_moderate(W_buy,W_sell) ## combining and running thr W moderate forumla 
            # print(self.W_moderate_list_within_class)

        self.ag, self.agpd,self.number_of_trade,self.average_day, self.day_std_deviation,self.revenue_per_year,self.absolut_trade_winrate,self.draw_win_winrate,self.draw_lose_winrate,self.lose_winrate = self.income() ## doing the final analysis and testing it through the past data by adding the virtual money and see
        self.average_volume = np.mean(self.list_of_volume_of_exchange)*self.list_of_ending_price[-1]  ## calucating the average of all
        # self.close()


    def print_info(self):
        print(f"Stock Symbol: {self.stock_symbol}")
        print(f"AGPD: {self.agpd}")
        print(f"Number of Trades: {self.number_of_trade}")
        print(f"Ending Price: {self.list_of_ending_price[-1]}")
        print(f"W Moderate List: {self.W_moderate_list}")

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

        while i < date_purchase: ## loop through the comparing date purchase
            # print("Which one are we are going to execute rn: ",self.list_of_date[int(self.comparing_date_purchase[int(i)])+1]) ## print the date that we are going to execute
            # if self.list_of_minimum_price[int(self.comparing_date_purchase[int(i)])] <= self.list_of_opening_price[int(self.comparing_date_purchase[int(i)])]*0.97: ## if the minimum price is less than the opening price*0.97
            #     print("We need to sell of early and not passing the past record")
            #     past_record = 0
            ## if the next day drop more than 3% and it is following the past recorrd => we need to overwrite that 
            # print("The past record is: ",past_record+1) ## print the past record
            # print("The comparing date purchase is: ",self.comparing_date_purchase[int(i)]) ## print the comparing date purchase
            if i > len(self.buy_at_ending_price):
                buy_in_array_pointer = -1 ## if the buy in array pointer exceeds the length of the buy at ending price, then we just set it to the last element

            if len(self.buy_at_ending_price) == len(self.sell_at_ending_price):
                if int(self.comparing_date_purchase[int(i)]+1) == len(self.list_of_opening_price) or int(self.comparing_date_purchase[int(i)]) == past_record+1:
                    i+=1 ## increment the  pointer value for the purchase date
                    # print("Has to pause for a bit")
                    continue
                self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.list_of_opening_price[int(self.comparing_date_purchase[int(i)])+1]) ## append the value to the list
                buying_date = np.append(buying_date,self.list_of_date[int(self.comparing_date_purchase[int(i)]+1)]) ## append the date to the buying date list => When we buy and append it to the list

                # print("The price that we are buying", self.list_of_opening_price[int(self.comparing_date_purchase[int(i)]+1)])
                # print("After appending to the buy list", self.buy_at_ending_price)            # print("the date that we are going to buy is:", self.comparing_date_purchase[int(i)])
                past_record = int(self.comparing_date_purchase[int(i)])
            j = 0 ## pointer value for the sell off date    
            while j < date_sell_off:
                if self.comparing_date_sell_off[int(j)] - self.comparing_date_purchase[int(i)]>=0:
                    self.actual_actual_purchase = np.append(self.actual_actual_purchase,self.comparing_date_purchase[int(i)]) ## append the value to the list
                    sell_early = False
                    drop_too_much = False
                    # print("We are tracking on the price: ", self.buy_at_ending_price[buy_in_array_pointer])
                    for k in range(int(self.comparing_date_purchase[(int(i))]+1),int(self.comparing_date_sell_off[(int(j))]+1)):
                        if self.list_of_maximum_price[k] >= self.buy_at_ending_price[buy_in_array_pointer]*1.03: ## if the maximum price is greater than the ending price*1.03
                            self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*1.03) ## append the value to the list
                            sell_early = True
                            # print("The sell early: ",self.buy_at_ending_price[buy_in_array_pointer]*1.03 )
                            selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
                            absolute_win_trade_count += 1 ## increment the absolute win trade count
                            break
                        elif self.list_of_minimum_price[k] <= self.buy_at_ending_price[buy_in_array_pointer]*0.97:
                            # print("This drop off early: ",self.list_of_opening_price[int(self.comparing_date_purchase[int(i)]+1)]*0.95 )
                            # print("The minimum price is: ",self.list_of_minimum_price[k])
                            # print("The comparing date purchase is: ",self.comparing_date_purchase)

                            # print("This drop off early: We shitted",self.buy_at_ending_price[buy_in_array_pointer]*0.97 )

                            self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*0.97)
                            drop_too_much = True
                            selling_date = np.append(selling_date,self.list_of_date[int(k)]) ## append the date to the selling date list => When we sell and append it to the list
                            lose_trade_count += 1 ## increment the lose trade count
                            # print("This drop off early: ",self.list_of_opening_price[int(self.comparing_date_purchase[int(i)]+1)]*0.95)
                            ## the hot added feature 
                            ## when broke and then we re - purchase again 
                            # print("Trigger here")
                            # print("the date that we are going to buy is: ",self.list_of_date[int(self.comparing_date_purchase[int(i)])])

                            # print("The k value is: ",k)

                            if self.comparing_date_purchase[(int(i))]+1 == k:
                                past_record = 0 ## reset the past record to something weird to avoid error
                                j+=1 ## increment the pointer value for the buy in date
                                # print("Remove past record and continue")
                                break ## if the date that we are buying date that we append is the same as the next day, then we just remove the past record and continue

                            if i+1 >= len(self.comparing_date_purchase): ## idfk trying to append if it exceeds the i+1
                                self.comparing_date_purchase = np.append(self.comparing_date_purchase,int(k)) ## append the value to the list
                            else:
                                self.comparing_date_purchase = np.insert(self.comparing_date_purchase,i+1,int(k)) ## append the value to the list
                            self.list_of_reflection = np.append(self.list_of_reflection,int(k)) ## append the value to the list # can not care for now
                            if i+1 >= len(self.buy_at_ending_price):
                                self.buy_at_ending_price = np.append(self.buy_at_ending_price,self.buy_at_ending_price[buy_in_array_pointer]*0.97)
                            else:
                                self.buy_at_ending_price = np.insert(self.buy_at_ending_price,i+1,self.buy_at_ending_price[buy_in_array_pointer]*0.97) ## append the value to the list
                            
                            # print("We are going to buy on this date",self.list_of_date[int(k)]) ## print the date that we are going to buy
                            buying_date = np.append(buying_date,self.list_of_date[int(k)]) ## append the date to the buying date list => When we buy and append it to the list
                            # date_purchase += 1 ## update the date purchase
                            past_record = int(k)-1 ## update the past record
                            # print("Updated past record to: ",self.list_of_date[int(past_record)]) ## print the past record

                            # print("The past record is updated to: ",past_record)
                            # print("The comparing date purchase is updated to: ",self.comparing_date_purchase)
                            # print("The buying price is updated to: ",self.buy_at_ending_price)
                            # print("The buying date is updated to: ",buying_date)
                            break

                    if not sell_early and not drop_too_much: ## if we didn't sell early / wait until W_sell >= 26
                        self.sell_at_ending_price = np.append(self.sell_at_ending_price,self.list_of_ending_price[int(self.comparing_date_sell_off[int(j)])])
                        selling_date = np.append(selling_date,self.list_of_date[int(self.comparing_date_sell_off[int(j)])]) ## append the date to the selling date list => When we sell and append it to the list  
                        draw_trade_count += 1 ## increment the draw trade count
                        draw_trade_start_day = np.append(draw_trade_start_day,self.list_of_date[int(self.comparing_date_purchase[int(i)])]) ## append the date to the draw trade start day list                  

                    # buying_date = np.append(buying_date,self.list_of_date[int(self.comparing_date_purchase[int(i)]+1)]) ## append the date to the buying date list => When we buy and append it to the list
                    break
                j+=1 ## increment the pointer value for the sell off date
            i+=1 ## increment the pointer value for the purchase date

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
        self.win_rate = win_trade/trade_count if trade_count > 0 else 0
        print("win rate : ",self.win_rate)
        print("Number of trades : ",len(self.elasped_day))
        self.average_day = average_day
        return ag,agpd,len(self.elasped_day),average_day,day_std_deviation,revenue_per_year,absolute_win_trade_count/trade_count,draw_win_trade_count/trade_count,draw_lost_trade_count/trade_count,lose_trade_count/trade_count
    
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

def document_overview_winrate(winrate_requirement:float):
        # Example usage of the try_out class
    stock_price_america = r"stock_list/nasdaqlisted.txt" ## getting the reference 

    filename = "generated_file/America/winrate_america_all_modified.txt" ## the fila that we are going to write on

    list_of_america = [] ## the list of all the stock symbol in America
    f= open(stock_price_america,"r",encoding="utf8") ## open the file
    strings = f.read().split("\n") ## read the file and split by new line
    strings = strings[1:-1]    ## remove the first and the last element

    for string in strings:  ## for each string in the strings
        list_of_america.append(string.split("|",1)[0])   ## split by the pipe and append to the list of america

    # list_of_america= ["XLO"]

    with open(filename,'a+') as f: ## prepare the file
        f.write("Stock_ID" + " " + "AGPD_value " + "Number_of_Trade"+ " "+"Average_Day" + " " + "Average_WinRate"+" "+"absolute_win_rate"+" "+"draw_win_rate" +" "+"draw_lose_rate"+" "+"lose_rate"   +"\n")

    for i in list_of_america:  ## for each stock symbol in the list of america
        try: 
            print(i) 
            a = try_out(i,W_buy = 17,W_sell =26) ## get the risk assessment library

            with open(filename, "a+") as f: ## open the file to write
                if (a.agpd > 0.001 and a.number_of_trade >= 4 and a.agpd != 1 and float(a.list_of_ending_price[-1]) >2 and a.W_moderate_list[-1] > 0 and a.average_volume > 500000):
                    f.write(i + "," + str(a.agpd) + "," + str(a.number_of_trade) + "," + str(a.average_day) + "," + str(a.win_rate) +","+str(a.absolut_trade_winrate)+","+str(a.draw_win_winrate)+","+str(a.draw_lose_winrate)+","+str(a.lose_winrate) +"\n")
        except IndexError:
            print("Index Error for stock symbol:", i)
            pass
        except FileNotFoundError:
            print("File Not found error for stock symbol:", i)
            pass
        except ZeroDivisionError:
            print("Zero Division Error for stock symbol:", i)
            pass
        except Exception as e:
            print(f"An error occurred for stock symbol {i}: {e}")
            pass


def exporting_to_document():
    '''
    This is the function that we use to export the data to a document

    -----------
    Parameters(Inputs):
    -----------
    * self: Just pass in the object

    -----------
    Returns:
    -----------
    None
    '''

    ## preparing the document 
    stock_price_america = r"stock_list/nasdaqlisted.txt" ## getting the reference 
    list_of_america = [] ## the list of all the stock symbol in America
    f= open(stock_price_america,"r",encoding="utf8") ## open the file
    strings = f.read().split("\n") ## read the file and split by new line
    strings = strings[1:-1]    ## remove the first and the last element

    for string in strings:  ## for each string in the strings
        list_of_america.append(string.split("|",1)[0])   ## split by the pipe and append to the list of america

    # list_of_america = ["KRYS"] ## just for testing purpose, we can remove this later onXLO
    for i in list_of_america:
        try:
            print(i)

            filename = "generated_file/America/stock_data/{}_modified.txt".format(i)

            a = try_out(i,W_buy = 17,W_sell =26) ## get the risk assessment library
            Path("generated_file/America/stock_data").mkdir(parents=True, exist_ok=True) ## create the directory if it does not exist
            with open(filename,'a+') as f: ## prepare the file
                f.write("Date,Opening_Price,Closing_Price,Maximum_Price,Minimum_Price,Volume_of_Exchange,MFI,RSI,K,D,W_moderate,W_sell\n") ## writing the header for the file

            for i in range(15,len(a.list_of_opening_price)):
                with open(filename, "a+") as f:
                    f.write(f"{a.list_of_date[i]},{a.list_of_opening_price[i]},{a.list_of_ending_price[i]},{a.list_of_maximum_price[i]},{a.list_of_minimum_price[i]},{a.list_of_volume_of_exchange[i]},{a.list_of_MFI[i-13]},{a.rsi_list[i-15]},{a.list_of_k_value[i-13]},{a.list_of_d_value[i-13]},{a.W_moderate_list[i-13]},{a.W_sell_list[i-13]}\n")
            print(f"Data for {a.stock_symbol} has been exported to {filename}")

        except IndexError:
            print("Index error for stock symbol:", i)
            pass

        except FileNotFoundError:
            print("File Not found error for stock symbol:", i)
            pass

        except ZeroDivisionError:
            print("Zero Division Error for stock symbol:", i)
            pass

        except Exception as e:
            print(e)
            pass




if __name__ == "__main__":



    stock_symbol = "AAME"  # Example stock symbol
    # trying = try_out(stock_symbol, W_buy=17, W_sell=26)  # Create an instance of the try_out class
    # Example usage of the try_out class
    document_overview_winrate(winrate_requirement=0.5)  # Document overview with a win rate requirement
    
    # exporting_to_document()  # Export the data to a document
    # print("Stock : " , stock_symbol)
    # try_out_instance = try_out(stock_symbol,W_buy =17,W_sell=26)
    # # try_out_instance.print_info()
    
    # W_buy = 17  # Example W_buy value
    # W_sell = 26  # Example W_sell value
    # W_moderate_list, W_sell_list = try_out_instance.W_moderate(W_buy, W_sell)
    
    # print("W Moderate List:", W_moderate_list)
    # print("W Sell List:", W_sell_list)

