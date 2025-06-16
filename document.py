from datetime import datetime
import numpy as np
from pathlib import Path
from risk_assessment_library import risk_assessment_library

class document():

    def __init__(self):
        self.current_datetime = datetime.now().strftime("%Y-%m-%d")

    def America(self,agpd=0.001,number_of_trade=4,ending_price=2,volume=500000):
        '''
        This function is to get the list of all the stock in America and return as a file, comprising of 
        the stock name, stock symbol, stock price, stock volume, stock market cap, stock sector, stock industry, stock country
        '''
        stock_price_america = r"stock_list/nasdaqlisted.txt" ## getting the reference 
        ## file from the stock list
        Path("generated_file").mkdir(parents=True, exist_ok=True) ## create the directory if it does not exist
        Path("generated_file/America").mkdir(parents=True, exist_ok=True) ## create the directory if it does not exist
        filename = "generated_file/America/agpd_america_" + str(self.current_datetime)+"_all_0.001.txt" ## the fila that we are going to write on

        list_of_america = [] ## the list of all the stock symbol in America
        f= open(stock_price_america,"r",encoding="utf8") ## open the file
        strings = f.read().split("\n") ## read the file and split by new line
        strings = strings[1:-1]    ## remove the first and the last element

        for string in strings:  ## for each string in the strings
            list_of_america.append(string.split("|",1)[0])   ## split by the pipe and append to the list of america

        ## Now we have the list of all the stock in America
        ## Now we need to get the stock price of all the stock in America

        with open(filename,'a+') as f: ## prepare the file
            ## writing the header for the file
            f.write("Stock_ID" + " " + "AGPD_value" + " Current_price "+ "Number_of_Trade"+ " "+"W_buy_value_now" + " " + "W_sell_value"+ " "+"day_last_update" + " "+"Average_day"+ " " + "Day_standard_deviation " +"W_moderate_%_diff"+" "+"five_day_average_of_W_buy"+ " "+"Days_have_been_below_17"+" "+"Averag_Volume"+"\n") 

        ## looping over all the stock symbol in America
        for i in list_of_america:
            try:
                ## signifying the stock symbol
                print(i)
                ## avoid the stock that is shitted
                if (i=="NCPL" or i == "NUKK" or i == "XBIOW" or i == "WTER" or i=="SHPW" or i =="ISPOW" or i == "LIDRW" or i == "NLSPW" or i == "VSSYW"):
                    continue

                a = risk_assessment_library(i) ## get the risk assessment library


                percentage_difference_in_W_moderate=(a.W_moderate_list[-1]-a.W_moderate_list[-2])/a.W_moderate_list[-2]*100
                five_day_average_of_W_buy = np.average(np.array(a.W_moderate_list[-6:-1]))
                days_have_been = a.days_has_been_below_17()
                print(a.average_volume)
                
                with open(filename, "a+") as f:
                    if (a.agpd > agpd and a.number_of_trade>= number_of_trade and a.agpd != 1 and float(a.list_of_ending_price[-1])>ending_price and a.W_moderate_list[-1] >0 and a.average_volume>volume):
                        f.write(i + "," + str(a.agpd) + "," + str(a.list_of_ending_price[-1]) + "," + str(a.number_of_trade) + "," + str(a.W_moderate_list[-1]) + "," + str(a.W_sell_list[-1]) + "," +str(a.list_of_date[-1])+ "," + str(a.average_day) + "," + str(a.day_std_deviation) + ","+ str(percentage_difference_in_W_moderate)+","+ str(five_day_average_of_W_buy) + ","+ str(days_have_been)+ ","+str(a.average_volume)+ "\n")

            except IndexError: 
                print("Index Error")
                pass
            except FileNotFoundError:
                # print(filename)
                print("File Not found error")
                pass

            except ZeroDivisionError:
                print("Zero ")
                pass 

            except Exception as e:
                print(e)
                pass


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
            a = risk_assessment_library(i,W_buy = 17,W_sell =26) ## get the risk assessment library

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

            a = risk_assessment_library(i,W_buy = 17,W_sell =26) ## get the risk assessment library
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
    d = document()
    d.America()

