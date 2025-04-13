from document import document
from datetime import datetime
from risk_assessment_library import risk_assessment_library

class auto(document):
    def __init__(self):
        pass


    def returning_the_list_of_under_17(self,W_value_requirment:int,agpd_value_requirment:int,number_of_trade_requirment:int,ending_price_requirment:int,average_day_requirement:int,volume_requirement:int)->list:
        '''
        Input: W_value_requirment, agpd_value_requirment, number_of_trade_requirment, ending_price_requirment, average_day_requirement

        This function will return the list of stock id which are 
        
        * under the W_value_requirment, average_day_requirement

        * and above agpd_value_requirment, number_of_trade_requirment, ending_price_requirment
        '''

        ## average day + 1 sigma < 20

        ## mean( all the stock's average day sigma)
        current_datetime = datetime.now().strftime("%Y-%m-%d")
        print(current_datetime)

        # filename_america = r"/home/ricky/Documents/site/agpd_america_" + str(current_datetime)+"_all_0.001.txt"
        filename_america = r"generated_file/America/agpd_america_"+str(current_datetime)+"_all_0.001.txt"
        # filename_america = r"/home/ricky/Documents/site/agpd_america_2024-10-31_all_0.001.txt"
        # filename_america = r"/home/ricky/Documents/site/agpd_america_2025-01-02_all_0.001.txt"

        result_array = [] 

        ## split string and identify the file
        with open(filename_america,'r') as f:
            strings = f.read().split("\n")
            strings = strings[1:-1]
            for string in strings:
                string = string.split(",")

                W_value = float(string[4]) ## recognise the sections in the file
                agpd = float(string[1]) 
                ending_price = float(string[2])
                number_of_trade = float(string[3])
                average_day = float(string[7])+float(string[8])
                real_volume = float(string[12])*ending_price ## calucating the real volume

                # print(a.predictiing_volume_of_exchange_using_ema())
                # print(string)
                if W_value <W_value_requirment and agpd>agpd_value_requirment and ending_price > ending_price_requirment and number_of_trade>number_of_trade_requirment and average_day<average_day_requirement:
                    # print(string)
                    # print(string[0])
                    # a = risk_assessment(string[0],"")
                    # print(string[0])

                    if real_volume > volume_requirement: ## more constraints
                        result_array.append([string[0],string[1],string[2],string[3],string[4],string[5],string[6],string[7],string[8],string[9],string[10]])
            
            ## Sort the result_array by the 4 th element
            result_array.sort(key = lambda x: x[1],reverse=True)
                        
            # print(result_array)
            return result_array
        
    def returning_the_list_of_above_40(self,W_value:int):
        '''
        This function will return the list of stock id which are above the W_value_requirment
        Return: a list of order symbol only
        '''
        current_datetime = datetime.now().strftime("%Y-%m-%d")
        print(current_datetime) ## print out debug message and know the current datetime

        filename_america = r"/home/ricky/Documents/site/agpd_america_" + str(current_datetime)+"_all_0.001.txt"
        # filename_america = r"/home/ricky/Documents/site/agpd_america_2024-10-31_all_0.001.txt"
        filename_america = r"W:\Trading\website-main\website-main\agpd_america_"+str(current_datetime)+"_all_0.001.txt"
        filename_america = r"generated_file/America/agpd_america_"+str(current_datetime)+"_all_0.001.txt"

        result_array = [] 

        with open(filename_america,'r') as f: ## reading the file
            strings = f.read().split("\n") ## split each string into different category
            strings = strings[1:-1] ## remove the first row
            for string in strings: ## getting the first string
                string = string.split(",") ## split each section 
                if float(string[4]) >W_value:  ## finding the one that we need
                    result_array.append(string[0]) ## append it to result
            
            # print(result_array)
            return result_array ## return it

if __name__ == "__main__":
    auto = auto()
    auto.returning_the_list_of_under_17(20,0.001,4,2,20,500000)
    # auto.returning_the_list_of_above_40(40)