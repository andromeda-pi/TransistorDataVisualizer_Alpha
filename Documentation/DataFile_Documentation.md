# Documentation for the `DataFile` object from TransistorDataVisulaizer
The `DataFile` is the current method by which the file path and name is transferred to the TransistorDataFileReader.py (imported as tdfr) file, which creates File objects. 

A `DataFile` is a `Dataclass` comprised of 3 parameters: 
* `file_path`: 
* `file_name`: The file location in your computer to the CSV file.
* `misc`:

In past iterations, the fls DataFiles were vital for transferring the necessary information to the TDFR module to create File objects. Now, it appears that this is not needed. 

`file_path`: 
Comprised of a character (which denotes test type), another character (denoting gate type) and following numbers (typically transistor number). An example is 'It7' where the first character denotes that the test is a current plot (based on the 'I'), the second character describing that the top gate was used (as shown by the 't') and the last characters showing it was device 7 that was used. 

There are two test types: 'I' for a current test and 'R' for a resistance test.
There are two gate types: 't' for top gate or 'b' for bottom gate operation.
Transistor number: can be anything, but is useful to differentaite tests from eachother.

### Example: Creating a `DataFile` from a file path and file name
Suppose you have a CSV file named `Id-Vds var const Vbgs_n1.csv` that you want to plot and get a feel for. 
`import TransistorDataFiles as fls
import TransistorDataVisualizer

DF = tdv.DataFile( 'Ib8', r'C:\ABSOLUTE_FILE_PATH\Device8\Id-Vds var const Vbgs_n1.csv' )
F = tdv.File(DF)
F.quick_plot3d(-1)
`
