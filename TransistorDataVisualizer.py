import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from csv import reader as csvreader
import csv

@dataclass
class DataFile:
    def __init__(self, name: str, path: str, misc = None):
        ''''''
        self.file_name:str = name
        self.file_path: str = path
        self.misc = misc
        # misc can store any other relevant info, like cryo, epoxy, data quality etc

    def print(self):
        print("Name: ", self.file_name)
        print("File Location: ", self.file_path)
        print(f"Miscellaneous: {self.misc}")

class File:
    def __init__(self, Datafile: DataFile):
        assert(type(Datafile) == DataFile)
        self.m_headers = []
        self.m_title: str
        self.m_gate_type: str = ''
        self.m_dim1_count: int
        self.m_dim2_count: int
        self.m_sweep_type: str
        self.file_type: str = Datafile.file_name
        self.m_datadict: dict = {}
        self.m_shape: tuple # 2D shape tuple
        self.m_intervals: dict # dim1 and dim2 intervals from 'start' to 'stop' in steps of 'step'
        self.m_intervals_info: dict
        self.__process_csv(Datafile.file_path)
        self.__process_interval()
        self.reshape_data()
        self.__check_missing_dims()


    def __process_csv(self, input_file):
        '''Scrapes all pertinent data from the easyEXPERT csv into the File object.'''
        with open(input_file, 'r') as csvfile:
            reader = csvreader(csvfile, delimiter = ',') # change contents to floats
            data_idx = 0 # data row index -- which row in specifically the numerical data columns we're at
            for row in reader: # each row is a list
                match row[0].strip():
                    case 'PrimitiveTest':
                        self.m_sweep_type = row[1].strip()
                    case 'TestParameter':
                        self.__process_TestParameters(row)
                    case 'Dimension1':
                        self.m_dim1_count = int(row[1])
                    case 'Dimension2':
                        self.m_dim2_count = int(row[1])
                    case 'AnalysisSetup':
                        if row[1].strip() == 'Analysis.Setup.Title':
                            self.m_title = row[2].strip()
                    case 'DataName': # This comes directly before the DataValue entries
                        for i, header in enumerate(row):
                            if i == 0:
                                continue
                            self.m_headers.append(header.strip())

                            # this allocates appropriately-sized numpy arrays for the data
                            self.m_datadict[header.strip()] = np.zeros( self.m_dim1_count * self.m_dim2_count )
                    case 'DataValue': # this inserts data into the appropriate data array spots
                        for i, v in enumerate(row):
                            if i == 0:
                                continue
                            self.m_datadict[self.m_headers[i-1]][data_idx] = float(v)
                        data_idx += 1
        self.m_shape = (self.m_dim2_count, self.m_dim1_count)

    def __process_TestParameters(self, row):
        """Fetches stop, start, and step/count interval information from eE (easyEXPERT) csv.
        This will then be used to construct the intervals of each dimension via process_interval()"""
        match row[1].strip():
            case 'Channel.VName':
                self.m_intervals = [ [row[2].strip(), {}], [row[3].strip(), {}] ]
            case 'Measurement.Primary.Stop':
                self.m_intervals[0][1]['stop'] = float(row[2].strip()) 
            case 'Measurement.Primary.Count':
                self.m_intervals[0][1]['count'] = int(row[2].strip()) 
            case 'Measurement.Primary.Step':
                self.m_intervals[0][1]['step'] = float(row[2].strip())
            case 'Measurement.Bias.Source':
                self.m_intervals[0][1]['start'] = float(row[2].strip()) 
                self.m_intervals[1][1]['start'] = float(row[3].strip())
            case 'Measurement.Secondary.Step':
                self.m_intervals[1][1]['step'] = float(row[2].strip())
            case 'Measurement.Secondary.Count':
                self.m_intervals[1][1]['count'] = int(row[2].strip())

        


    def __process_interval(self):
        """Creates the v1, v2 intervals via [start, start+step, ... stop-step, stop].
        Overwrites self.m_intervals w/ new intervals. Calculates start/step/stop when necessary.
        Goal is to get stop, start, and step params to make the intervals using np.arange()
        Step is frequently determined via the 'count' param if 'step' DNE already"""
        intervals, intervals_info = {}, {}
        v1_name, v2_name = self.m_intervals[0][0], self.m_intervals[1][0]
        v1_start, v2_start = self.m_intervals[0][1]['start'], self.m_intervals[1][1]['start']

        # get the first voltage v1's interval
        v1_stop = self.m_intervals[0][1]['stop']
        if 'count' in self.m_intervals[0][1].keys():
            v1_count = self.m_intervals[0][1]['count']
            v1_step = (v1_stop - v1_start) / (v1_count - 1) # count-1 so it doesn't count the start
        elif 'step' in self.m_intervals[0][1].keys():
            v1_step = self.m_intervals[0][1]['step']
        intervals[v1_name] = np.arange(v1_start, (v1_stop+v1_step), v1_step)
        intervals_info[v1_name] = {"start": v1_start, 
                                   "stop": v1_stop, 
                                   "step": v1_step, 
                                   "count": len(intervals[v1_name])}

        # get the second voltage v2's interval
        if 'step' and 'count' in self.m_intervals[1][1].keys(): # multiple data rows
            v2_count = self.m_intervals[1][1]['count']
            v2_step = self.m_intervals[1][1]['step']
            v2_stop = v2_start + (v2_count-1) * v2_step # count-1 so it doesn't recount the start
            intervals[v2_name] = np.arange(v2_start, (v2_stop+v2_step), v2_step)
        else:
            intervals[v2_name] = np.array([v2_start]) # a single row of data
            v2_count = 1
            v2_step = 0
            v2_stop = v2_start
        intervals_info[v2_name] = {"start": v2_start, "stop": v2_stop, "step": v2_step, "count": v2_count}
        
        self.m_intervals_info = intervals_info
        self.m_intervals = intervals


    def __check_missing_dims(self):
        """This function checks to see if there are independent variables NOT in m_datadict.
        If missing variables are found, then a 2D numpy array is created via the meshgrid."""
        header_keys = self.m_headers 
        # header_keys may or may not contain all interval keys. This determined later on.

        interval_keys = list(self.m_intervals.keys())
        # interval_keys will contain 2 entries: each independent variable voltage

        keys = ['', ''] # this list will store the order of interval keys
        for i in [0, 1]:
            if not interval_keys[i] in header_keys: # if the i-th interval key is NOT in the header keys...
                keys[1] = interval_keys[i] # set keys[1] to the missing key                    
            else:
                keys[0] = interval_keys[i] # set keys[0] to the present key
        if keys[1]: # if there was an interval key that was missing from the headers keys
            # create the missing 2D array that would go with the missing independent variable using a meshgrid
            x, y = np.meshgrid(self.m_intervals[interval_keys[0]], self.m_intervals[interval_keys[1]])
            # and add it to the m_headers as the 2nd independent variable
            self.m_headers.insert(1, keys[1])
            self.m_datadict[keys[1]] = y
    

    def reshape_data(self, reverse = False):
        """Untested function, beware. It is supposed flip data along the x = y line."""
        for key in self.m_headers:
            if reverse:
                self.m_datadict[key] = np.reshape(self.m_datadict[key], (self.m_dim1_count, self.m_dim2_count))
            else:
                self.m_datadict[key] = np.reshape(self.m_datadict[key], (self.m_dim2_count, self.m_dim1_count))
    

    def print(self):
        """Prints the headers and numpy shape of the data arrays"""
        print(self.m_headers)
        print(self.m_shape)

    def make_meshgrid(self):
        """Creates a meshgrid from the two independent variables"""
        keys = []
        things = []
        for key in self.m_intervals.keys():
            keys.append(key)
        return np.meshgrid(self.m_intervals[keys[0]], self.m_intervals[keys[1]])
    

    def quick_plot3d(self, Zindex:int, connectors:bool = True):
        """Creates a 3D plot of the data, with the Z axis selected via Zindex

        Input: 
            Zindex: index the Z-data will be pulled from. If 0 or 1, will be the same as X or Y data. 
                Suggested to set Zindex to -1 or -2.
            connectors: Bool of whether to have the wireframe object automatically connect points.   
        """
        if Zindex >= len(self.m_headers):
            print(f"Zindex [{Zindex}] out of bounds of data with len = {len(self.m_headers)}")
            return
        x, y = self.get_data(0), self.get_data(1)
        z = self.get_data(Zindex)
        fig, ax1 = plt.subplots(
            1, 1, #figsize = (12, 18),
            subplot_kw={'projection': '3d'})
        if connectors:
            ax1.plot_wireframe(x, y, z, rcount=self.m_dim2_count, ccount=self.m_dim1_count)#cstride=file.m_dim2_count)
        else:
            ax1.plot_wireframe(x, y, z, rcount=self.m_dim2_count, ccount=0)#cstride=file.m_dim2_count)
    
        ax1.set_xlabel(self.get_data_name(0))
        ax1.set_ylabel(self.get_data_name(1))
        ax1.set_zlabel(self.get_data_name(Zindex))
        ax1.set_title(self.get_title())
        plt.show()

    def quick_plot3d_data(self, X:list, Y:list, Z:list, connectors:bool = True):
        """Creates a 3D plot of the X, Y, Z data according to the combinations of (X[i,j],Y[i,j],Z[i,j]) coordinate triplets.
        X and Y are typically the product of the NumPy.meshgrid(x:1Dlist, y:1Dlist) which will return (X, Y)
        
        Input: 
            X is a 2D list of values that vary column to column but not row to row
            Y is a 2D list of values that vary row to row but not column to column
            Z is a 2D list of values that map each 
            connectors: bool of whether to have the wireframe object automatically connect points.
        """
        fig, ax1 = plt.subplots(
            1, 1, figsize = (12, 18),
            subplot_kw={'projection': '3d'})
        if connectors:
            ax1.plot_wireframe(X, Y, Z, rcount=self.m_dim2_count, ccount=self.m_dim1_count)#cstride=file.m_dim2_count)
        else:
            ax1.plot_wireframe(X, Y, Z, rcount=self.m_dim2_count, ccount=0)#cstride=file.m_dim2_count)
    
        ax1.set_xlabel(self.get_data_name(0))
        ax1.set_ylabel(self.get_data_name(1))
        #ax1.set_zlabel()
        ax1.set_title(self.get_title())
        plt.show()

    def get_data(self, index: int):
        return self.m_datadict[self.m_headers[index]]
    
    def get_data_name(self, index: int):
        return self.m_headers[index]
    
    def get_headers(self):
        return self.m_headers
    
    def get_interval(self, index: int):
        return self.m_intervals[self.m_headers[index]]
    
    def get_interval_name(self, index: int) -> str:
        return self.m_intervals.keys()[self.m_headers[index]]
    
    def get_title(self):
        """Returns m_title"""
        return self.m_title
    
    def get_interval_info(self, index: int) -> dict:
        """Returns the interval_info of the data at index specified."""
        return self.m_intervals_info[self.m_headers[index]]
    
    def get_slicing(self, axis, domain: list[float, float]) -> tuple[int, int]:
        """Returns a tuple for index slicing to reduce the x or y axis to the domain [a, b] via x[:, a:b] or y[a:b, :]
        
        Input:  axis ->'x' or 0 or 'y' or 1 to select axis
                domain -> [a, b] to restrict given axis to
                
        Ouptut: tuple for index slicing of form (a, b)"""
        if axis == 0 or axis == 'x':
            xdom = domain
            x = self.get_data(0)
            cols = (np.searchsorted(x[0,:], xdom[0]),    np.searchsorted(x[0, :], xdom[1], side='right'))
            return cols
        elif axis == 1 or axis == 'y':
            ydom = domain
            y = self.get_data(1)
            rows = (np.searchsorted(y[:, 0], ydom[0]),    np.searchsorted(y[:, 0], ydom[1], side='right'))
            return rows
        else:
            print("Invalid axis selection. Enter either the axis index or character (ei. 'x' or 0; 'y' or 1)")
            return None
        
        """
        For the proper index slicing, x values vary column to column, so you need to hold the row constant
        and vary the column indices. For the y values, y values are constant from column to column and vary 
        row by row, so you need to do the index slicing where you hold the columns constant and change the row.
        This ultimately comes out to looking like: x val var = x[0, :]  ;  y val var = y[:, 0]

        Then, to properly do the slicing of the data arrarows, since x correpsonds to changes in the rows and 
        y corresponds to changes in the columns, the ordering of the index slicing should be like this:
        xtrimmed = x[ rows[0]:rows[1], cols[0]:cols[1] ]
        ytrimmed = y[ rows[0]:rows[1], cols[0]:cols[1] ]
        """

# @dataclass
class DataInfo:
    def __init__(self):
        self.data_name: str = ''
        self.graph_type: int = -1
        self.trans_num = -1
        self.trans_model: str = ''
        self.units = {'x': '', 'y': '', 'z': ''}
        self.chan_dims = {'len': '', 'wid': '', 'area': ''}
        self.gate: str = ''

    def print(self):
        print(f"Data set name: {self.data_name}")
        print(f"Gate ID: {self.gate}")
        print(f"Graph preset selection: {self.graph_type}")
        print(f"Transistor number: {self.trans_num}")
        print(f"Dimensions: {self.chan_dims['len']} x {self.chan_dims['wid']} = {self.chan_dims['area']}")
        print(f"Units: x ({self.units['x']}); y ({self.units['y']}); z ({self.units['z']})")
        
    def copy_from(self, Info):
        self.data_name = Info.data_name
        self.graph_type = Info.graph_type
        self.trans_num = Info.trans_num
        self.trans_model = Info.trans_model
        self.units= Info.units
        self.chan_dims = Info.chan_dims
        self.gate = Info.gate

    def make_copy(self):
        copy = DataInfo()
        copy.data_name = self.data_name
        copy.graph_type = self.graph_type
        copy.trans_num = self.trans_num
        copy.trans_model = self.trans_model
        copy.units= self.units
        copy.chan_dims = self.chan_dims
        copy.gate = self.gate
        return copy


class DataSet(File):
    def __init__(self, DataFile: DataFile):
        super().__init__(DataFile)
        self.Info = DataInfo()
        self.ln_style = '-'
        self.marker = '.'
        self.Info.data_name = DataFile.file_name 
        # self.title: str
        self.color = [0.5, 0.5, 0.5]
        self.parse_data_name(DataFile.file_name) # 1 char, 1 char, #'s numbers (graph type, gate, item number)

    def print(self, with_data_info = False, with_data = False):
        """Prints DataSet's information"""
        self.Info.print()
        print(f"Line color RGB = {self.color}")
        print(f"Line stye: {self.ln_style}")
        print(f"Line marker: {self.marker}")

        if with_data_info:
            print(self.m_headers)
            print(f"X has length of {len(self.m_x_data)}")
            for i,x in enumerate(self.m_y_data):
                print(f"Y's {i} column has length of {len(x)}")
        if with_data:
            print(self.m_x_data)
            print(self.m_y_data)
    
    def parse_data_name(self, data_name):
        """Sets the DataSet's meta info from the 3 character test code data_name"""
        self.parse_graph_type(data_name[0])

        if data_name[1] == 'b':
            self.Info.gate = 'bottom'
            self.ln_style = '--'
        elif data_name[1] == 't':
            self.Info.gate = 'top'
            self.ln_style = '-'
        else:
            print("Error: data_name[1] is not readable gate 'b' or 't'.")

        self.parse_trans_num(data_name[2:])

    def set_colors(self, r, b, g):
        self.color = [r, b, g]
    
    def set_color(self, num):
        match num:
            case 0:
                self.set_colors(0.5, 0.5, 0.5)# self.set_colors(0, 0, 0)
            case 1:
                self.set_colors(1, 0, 0)
            case 2:
                self.set_colors(0, 0, 1)
            case 3:
                self.set_colors(1, 0, 1) 
            case 4:
                self.set_colors(0, 0.8, 0.8) #self.set_colors(0, 1, 1)
            case 5:
                self.set_colors(0, 1, 0)
            case 6:
                self.set_colors(1, 1, 0)
            case _: 
                self.set_color(num-6)
    
    def set_marker(self, num: int):
        markers = ['.', '3', '*', '4', 'v', 'o']
        if num < 7:
            self.marker = markers[num]
        else:
            self.set_marker(num-6)

    def set_lnstyle(self, style: str):
        self.ln_style = style

    def scale_color(self, scale):
        for i in range(3):
            self.color[i] *= scale


    def parse_graph_type(self, char: str):
        if char.lower() == 'r':
            self.Info.graph_type = 0
            self.Info.units['x'] = 'V'
            self.Info.units['y'] = 'V'
            self.Info.units['z'] = 'Ω'
            # self.Info.x_unit = 'V'
            # self.Info.y_unit = 'Ω'        
        elif char.lower() == 'i':
            self.Info.graph_type = 1
            self.Info.units['x'] = 'V'
            self.Info.units['y'] = 'V'
            self.Info.units['z'] = 'A'
            # self.Info.x_unit = 'V'
            # self.Info.y_unit = 'A'
        else: 
            print("Error: data_name[0] is not readable gate 'R' or 'I'.")

    
    def parse_trans_num(self, transistor_number: str):
        #this can be expanded later to automatically grab dimensions
        tnum = int(transistor_number)
        if tnum in [2, 4, 7, 8]:
            self.Info.chan_dims['len'] = 50
            self.Info.chan_dims['wid'] = 50 
            self.Info.chan_dims['area'] = 50 * 50 #{'len': '', 'wid': '', 'area': ''}
            # self.Info.length = 50
            # self.Info.width = 50
        elif tnum == 3:
            self.Info.chan_dims['len'] = 100
            self.Info.chan_dims['wid'] = 100
            self.Info.chan_dims['area'] = 100 * 100 
        elif tnum == 6:
            self.Info.chan_dims['len'] = 200
            self.Info.chan_dims['wid'] = 200
            self.Info.chan_dims['area'] = 200 * 200
        else:
            self.Info.chan_dims['len'] = "unknown"
            self.Info.chan_dims['wid'] = "unknown"
            self.Info.chan_dims['area'] = "unknown"
        if tnum < 9:
            self.Info.trans_model = 'S31'
        else:
            self.Info.trans_model = "unknown"
        self.Info.trans_num = transistor_number  




class DataBank:
    def __init__(self, Set: DataSet = None):
        self.m_DataSets = []
        self.X: list = []
        self.Y: list = []
        self.Z: list = []
        self.domain: dict[str, list[float]] = {'x': (-float('inf'),float('inf')),
                        'y': (-float('inf'),float('inf')),
                        'z': (-float('inf'),float('inf'))
                        }
        self.auto_labels: bool = True
        self.connectors: bool = False
        self.Bank_Info: DataInfo = None
        self.override: bool = False
        if Set:
            self.append(Set)

    def change_Set_color(self, SetIndex: int, color: list[float,float,float]):
        """Method to change a DataSet at index SetIndex to the RGB input color"""
        print(f"Data Set #{SetIndex} color changed from {self.m_DataSets[SetIndex].color}")
        self.m_DataSets[SetIndex] = color
        print(f"to {self.m_DataSets[SetIndex].color}")

    def process_axis(self, axis, num_output=False):
        valid_axis = False
        for i, v in enumerate(['x','y','z']):
            if axis == i or axis == v:
                if not num_output:
                    axis = v
                    valid_axis = True
                else:
                    axis = i
                    valid_axis = True
        if not valid_axis:
            raise Exception("Error: invalid axis selected. Pick from 'x'/0, 'y'/1, or 'z'/2")
        return axis
   
    def append(self, Set: DataSet):
        """Method for appending DataSets to the DataBank"""
        assert(type(Set) == DataSet)

        s_count = len(self.m_DataSets)
        if s_count == 0:
            self.m_DataSets.append(Set)
            self.Bank_Info = Set.Info.make_copy()
            Set.set_color(s_count)
        elif Set.Info.gate == self.Bank_Info.gate and Set.Info.graph_type == self.Bank_Info.graph_type:
            Set.set_color(s_count)
            Set.set_marker(s_count)
            self.m_DataSets.append(Set)
            Set.set_color(s_count)
        else:
            if self.override:
                Set.set_color(s_count)
                Set.set_marker(s_count)
                self.m_DataSets.append(Set)
                Set.set_color(s_count)
            else:
                print("Mismatching gate/graph type. Cannot add this data to current set without override.")

    def add_from_DataFile(self, DataFile: DataFile, y_col:list = [], x_col:int = 0):
        if not y_col:
            #print("Using this Data Bank's default y_col selection...")
            y_col = self.m_DataSets[0].col_info[1]
        if not x_col:
            #print("Uisng this Data Bank's default x_col selection...")
            x_col = self.m_DataSets[0].col_info[0]
        Set = DataSet(DataFile, x_col, y_col)
        #print("Adding Set...")
        self.append(Set)


    def print(self):
        """Prints info about the DataBank and the stored DataSets"""
        length = len(self.m_DataSets)
        print(f"Data Set count: {length}")
        if length == 0:
            print("No data sets loaded.")
            return
        print(f"Data Set length info:")
        for i in range(length):
            print(f" Data Set {i}'s x length: {self.m_DataSets[i].m_dim1_count}")
            print(f" Data Set {i}'s y length: {self.m_DataSets[i].m_dim2_count}")
        print(f"Data bank's gate type: {self.Bank_Info.gate}")
        print(f"Data bank's graph setting: {self.Bank_Info.graph_type}")

    def make_auto_labels(self, xlbl, ylbl, zlbl):
        """Returns automatically created labels from 
        """
        if ylbl in ['Vgs', 'Vtgs', 'Vbgs']:
            ylbl = r'Gate Voltage $V_{GS}$ (V)'
        elif ylbl == 'Vds':
            ylbl = r'Drain-Source Voltage $V_{DS}$ (V)'

        if xlbl in ['Vgs', 'Vtgs', 'Vbgs']:
            xlbl = r'Gate Voltage $V_{GS}$ (V)'
        elif xlbl == 'Vds':
            xlbl = r'Drain-Source Voltage $V_{DS}$ (V)'

        if zlbl == 'R':
            zlbl = r'Resistance $R_D$ (Ω)'
        elif zlbl == 'Rk':
            zlbl = r'Resistance $R_D$ (kΩ)'
        elif zlbl in ['I', 'Id']:
            zlbl = r'Drain Current $I_D$ (A)'
        elif zlbl == 'Im':
            zlbl = r'Drain Current $I_D$ (mA)'
        elif zlbl == 'Iu':
            zlbl = r'Drain Current $I_D$ (μA)'
        lbls = [xlbl, ylbl, zlbl]
        return lbls

    

    def quick_plot3d(self, Zindex = -1):
        """Displays a 3D plot of the DataBank's contents with 
        user-set domain restriction, potential auto-labeling, and possible connectors.
        """

        fig, ax1 = plt.subplots(
            1, 1, 
            # figsize = (12, 18),
            subplot_kw={'projection': '3d'})
        
        if len(self.m_DataSets) == 0:
            print("No data loaded, empty plot generated")
            plt.show()
            return      

        labels = [self.m_DataSets[0].get_data_name(0),
                    self.m_DataSets[0].get_data_name(1),
                    self.m_DataSets[0].get_data_name(Zindex)]
        if self.auto_labels:
            labels = self.make_auto_labels(labels[0], labels[1], labels[2])

        ax1.set_xlabel(labels[0])
        ax1.set_ylabel(labels[1])
        ax1.set_zlabel(labels[2])

        ax1.set_title(self.Bank_Info.data_name)
        
        for i, S in enumerate(self.m_DataSets):
            x, y = S.get_data(0), S.get_data(1)
            z = S.get_data(Zindex)
            dim1, dim2 = S.m_dim1_count, S.m_dim2_count

            cols = S.get_slicing('x', self.domain['x'])
            rows = S.get_slicing('y', self.domain['y'])

            color = S.color
            name = S.Info.data_name

            if self.connectors:
                col_counts = dim1
            else:
                col_counts = 0

            ax1.plot_wireframe( x[ rows[0]:rows[1], cols[0]:cols[1] ],
                                y[ rows[0]:rows[1], cols[0]:cols[1] ],
                                z[ rows[0]:rows[1], cols[0]:cols[1] ], 
                                rcount=dim2, 
                                ccount= col_counts,
                                color = color,
                                label = name)

        plt.show()
        


    def quick_div_plot3d(self, DivSet: DataSet, divIdx, drop_zeros=True, tolerance: float = -1, Zindex=-1):
        """Displays a 3D plot of the DataBank's contents relative to the dividing DataSet. 
        """
        
        div_data_dims = (DivSet.m_dim1_count, DivSet.m_dim2_count)

        fig, ax1 = plt.subplots(
            1, 1, 
            # figsize = (12, 18),
            subplot_kw={'projection': '3d'})
        
        if len(self.m_DataSets) == 0:
            print("No data loaded, empty plot generated")
            plt.show()
            return

        labels = [self.m_DataSets[0].get_data_name(0),
                  self.m_DataSets[0].get_data_name(1),
                  f"{self.m_DataSets[0].get_data_name(Zindex)}/{DivSet.get_data_name(divIdx)}"]
        if self.auto_labels:
            temp = self.make_auto_labels(labels[0], labels[1], labels[2])
            labels[0] = temp[0]
            labels[1] = temp[1]

        ax1.set_xlabel(labels[0])
        ax1.set_ylabel(labels[1])
        ax1.set_zlabel('Relative Performance')

        ax1.set_title(self.Bank_Info.data_name)
        X, Y, Z = [], [], []
        colors, names, dim1s, dim2s = [], [], [], []
        for i, S in enumerate(self.m_DataSets):
            S_data_dims = (S.m_dim1_count, S.m_dim2_count)

            # if dimensinos mismatch, omit the data set
            if S_data_dims != div_data_dims:
                print(f"DataSet at index ({i}) does not have matching x,y array dimensions of the dividing DataSet")
                print(f"\t{S_data_dims} =/= {div_data_dims}")
                print(f"Skipping DataSet ({i}) in DataBank")
                # add a "skipped DataSets" list here to keep track of for labelling later down the line
                continue

            zdiv = DivSet.get_data(divIdx)
            x = S.get_data(0)
            y = S.get_data(1)
            z = S.get_data(Zindex)
            if drop_zeros:
                zdiv, x, y, z = self.drop_zeros([zdiv, x, y, z], tolerance)

            dim1s.append(S.m_dim1_count)
            dim2s.append(S.m_dim2_count)

            cols = self.get_slicing('x', self.domain['x'], x)
            rows = self.get_slicing('y', self.domain['y'], y)

            X.append(x[ rows[0]:rows[1], cols[0]:cols[1] ])
            Y.append(y[ rows[0]:rows[1], cols[0]:cols[1] ])
            Z.append(z[ rows[0]:rows[1], cols[0]:cols[1] ] / zdiv[ rows[0]:rows[1], cols[0]:cols[1] ])

            colors.append( S.color )
            names.append( S.Info.data_name )
        
        for i in range(len(X)):
            if self.connectors:
                col_counts = dim1s[i]
            else:
                col_counts = 0

            ax1.plot_wireframe(X[i], Y[i], Z[i], 
                                rcount=dim2s[i], 
                                ccount=col_counts,
                                color = colors[i],
                                label = names[i])#cstride=file.m_dim2_count)
        plt.show()
    
    def print_indices(self, labels = False):   
        '''Prints off indices of the corresponding axis label'''     
        for i, S in enumerate(self.m_DataSets):
            print(f"For data set {i}:")

            if labels:
                print(" index\theader\taxis label")
                ax_labels = []

            else:
                print(" index\theader")
            
            headers = S.get_headers()
            for j, h in enumerate(headers):
                
                if labels:
                    if j == 0:
                        ax_labels = self.make_auto_labels(headers[0], headers[1], headers[2])
                    elif j > 2:
                        temp = self.make_auto_labels(headers[0], headers[1], headers[j])
                        ax_labels.append(temp[2])
                    print(f"   {j}\t {h}\t {ax_labels[j]}")

                else:
                    print(f"   {j}\t {h}")


    def set_domain(self, axis: str, domain: list[float, float], show=False):
        """[a, b] restricts the domain on the provided axis to be between the values a and b. 
        """
        if axis == 0 or axis == 'x':
            self.domain['x'] = tuple(domain)
        elif axis == 1 or axis == 'y':
            self.domain['y'] = tuple(domain)
        else:
            print(f"Axis '{axis}' is not a valid axis choice. Select from either 'x'/0 or 'y'/1.")
        if show:
            print(f"Domain now:\n{self.domain}")

    def reset_domain(self):
        self.domain = {'x': (-float('inf'), float('inf')), 'y': (-float('inf'), float('inf')), 'z': (-float('inf'), float('inf'))}
        
    
    def pop(self, i:int =-1) -> DataSet:
        """Akin to str pop method. If len(m_DataSets) becomes 0, Bank_Info resets to None type"""
        S = self.m_DataSets.pop(i)
        if len(self.m_DataSets) == 0:
            self.Bank_Info: DataInfo = None
        return S
    
    def create_projection_mapping(self, X2: list):
        """creates a dictionary of valid column indices as keys and
          corresponding valid DataSet indices"""
        meta_col_data = {}
        meta_color_data = {}
        for s, v in enumerate(X2): # for each DataSet # and list of values
            ncols = len(v) # finds number of columns in X2 data
            meta_color_data[s] = np.linspace(0.2, 1, ncols) # creates different shading factors based on X2 depth
            for c in range(ncols): # for each 
                if c in meta_col_data:
                    meta_col_data[c].append(s) # append the DataSet index s to the list of valid column indices 
                else:
                    meta_col_data[c] = [s] # make a new key-value pair of column index and DataSet index
        return meta_col_data, meta_color_data


    def quick_plot2d(self, x_idx, y_idx):
        """Given the selected independent x-axis and dependent y-axis, generate a 2D plot projected
            onto the second independent x2-axis, representing x2 via greyscaling.
        Input: 
            x_idx = 'x'/'y' or 0/1 and will select data for x-axis of 2D plot
            y_idx = 2/3/-1 and will select data for y-axis of 2D plot
                  the non-selected independent axis will be represented via sidebar 
            hint: to know which index correpsonds to what header, use the get_indices() method    
        """
        if len(self.m_DataSets) == 0:
            print("No data loaded, empty plot generated")
            plt.show()
            return

        if x_idx in [0, 'x']:
            x_idx = [0, 'x']
            x2_idx = [1, 'y']
        elif x_idx in [1, 'y']:
            x_idx = [1, 'y']
            x2_idx = [0, 'x']
        else:
            print(" Error: Invalid x_idx, choose from 0/'x' or 1/'y'")
            return

        fig, ax1 = plt.subplots(
            1, figsize = (6, 4))

        X, X2, Y = [], [], []
        markers, colors, names = [], [], []
        # line_names = []  

        labels = [self.m_DataSets[0].get_data_name(x_idx[0]),
                    self.m_DataSets[0].get_data_name(x2_idx[0]),
                    self.m_DataSets[0].get_data_name(y_idx)]
        if self.auto_labels:
            labels = self.make_auto_labels(labels[0], labels[1], labels[2])

        ax1.set_xlabel(labels[0]) # sets x label on 2d plot
        ax1.set_ylabel(labels[2]) # sets y label on 2d plot

        ax1.set_title(self.Bank_Info.data_name)

        for S in self.m_DataSets:
            x: list = S.get_data(x_idx[0])
            x2: list= S.get_data(x2_idx[0])
            y: list = S.get_data(y_idx)
            
            if x2_idx[0]: # if x2_idx is the 2nd indep variable (corresponding to y axis in 3d plot)
                cols = S.get_slicing(x_idx[0], self.domain[x_idx[1]]) # x vars by columns
                rows = S.get_slicing(x2_idx[0], self.domain[x2_idx[1]]) # y vars by rows
                x2 = x2[ rows[0]:rows[1], 0 ]
                x = x[ 0, cols[0]:cols[1] ]
                y = y[ rows[0]:rows[1], cols[0]:cols[1] ]
                rc_reversal = False # the order of rows and columns is preserved
            else:
                # x varies by columns and y varies by rows, so if x_idx == 'y' and x2_idx == 'x'
                #   then the row and column slicing must be swapped accordingly.
                rows = S.get_slicing(x_idx[0], self.domain[x_idx[1]]) 
                cols = S.get_slicing(x2_idx[0], self.domain[x2_idx[1]]) 
                x2 = x2[ 0, cols[0]: cols[1] ]
                x = x[ rows[0]:rows[1], 0 ]
                y = y[ rows[0]:rows[1], cols[0]:cols[1] ]
                rc_reversal = True # the order of rows and columns is flipped
            dim1, dim2, ydim = len(x), len(x2), len(y)

            X.append( x )
            X2.append(x2)
            Y.append( y )

            if rc_reversal and S.marker == '.':
                markers.append(',')
            else:
                markers.append(S.marker)
            colors.append(np.array(S.color))
            names.append(S.Info.data_name)

        meta_col_data, meta_color_data = self.create_projection_mapping(X2)
    
        for col, sets in meta_col_data.items():
            for s in sets:
                if not rc_reversal:
                    ax1.plot(X[s], Y[s][col, :], 
                             color = meta_color_data[s][col] * colors[s],
                             marker = markers[s])
                else:
                    ax1.scatter(X[s], Y[s][:, col], 
                                color = meta_color_data[s][col] * colors[s], 
                                marker = markers[s])
                                #marker='.')
        plt.show()

    def get_slicing(self, axis, domain: list[float, float], Array2D: np.array) -> tuple[int, int]:
        """Returns a tuple for index slicing to reduce the x or y axis to the domain [a, b] via x[:, a:b] or y[a:b, :]
        
        Input:  DataSet -> bnk.DataSet object you want sliced
                axis ->'x' or 0 or 'y' or 1 to select axis
                domain -> [a, b] to restrict given axis to

                
        Ouptut: tuple for index slicing of form (a, b)
                0/'x' -> cols
                1/'y' -> rows"""

        if axis in [0, 'x']:
            xdom = domain
            cols = (np.searchsorted(Array2D[0,:], xdom[0]),  np.searchsorted(Array2D[0, :], xdom[1], side='right'))
            return cols
        elif axis in [1, 'y']:
            ydom = domain
            rows = (np.searchsorted(Array2D[:,0], ydom[0]),  np.searchsorted(Array2D[:, 0], ydom[1], side='right'))
            return rows
        else:
            print("Invalid axis selection. Enter either the axis index or character (ei. 'x' or 0; 'y' or 1)")
            return None
        
        """
        For the proper index slicing, x values vary column to column, so you need to hold the row constant
        and vary the column indices. For the y values, y values are constant from column to column and vary 
        row by row, so you need to do the index slicing where you hold the columns constant and change the row.
        This ultimately comes out to looking like: x val var = x[0, :]  ;  y val var = y[:, 0]

        Then, to properly do the slicing of the data arrarows, since x correpsonds to changes in the rows and 
        y corresponds to changes in the columns, the ordering of the index slicing should be like this:
        xtrimmed = x[ rows[0]:rows[1], cols[0]:cols[1] ]
        ytrimmed = y[ rows[0]:rows[1], cols[0]:cols[1] ]
        """

    def drop_zeros(self, arrays: list[np.array], tolerance: float = -1)->list[np.array]:
        """Input a list of np.arrays of the same dimensions. Finds the columns and rows that are all zero in arrays[0],
        Drops the rows/columns of the 0th element of the input array that are all zeros from all arrays in the input.
        
        Input: arrays: list[np.array] -> arrays to drop zeros from using 0th item to determine what to drop
        
        Output: list[np.array] with rows/colums of zeros dropped"""
        drop_arr = arrays[0].copy()
        if tolerance == -1:
            min = np.min(np.absolute(drop_arr))
            var = np.var(drop_arr)
            tolerance = min+var

        drop_arr = arrays[0].copy()
        drop_arr[np.absolute(drop_arr) <= tolerance] = 0

        zero_rows = [i for i in range(drop_arr.shape[0]) if not drop_arr[i,:].any()]
        zero_cols = [i for i in range(drop_arr.shape[1]) if not drop_arr[:,i].any()]

        for i in range(len(arrays)):     
            arrays[i] = np.delete(arrays[i], zero_rows, axis=0)
            arrays[i] = np.delete(arrays[i], zero_cols, axis=1)   

        return arrays
