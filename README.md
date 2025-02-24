# TransistorDataVisualizer (tdv) (alpha release)
A Python package for quickly plotting easyEXPERT CSV files

Creating Plots:
```
# import the main package (alpha version)
import TransistorDataVisualizer as tdv

# import the file mappings
import TransistorDataFiles as fls
# if your file setup is different, change it in the above package and resave it
```

### tdv has several data structures

## DataFile: 
Stores the file location and test type for a CSV file.

### DataFile.file_name
Comprised of a character (which denotes test type), another character (denoting gate type) and following numbers (typically transistor number). An example is 'It7' where the first character denotes that the test is a current plot (based on the 'I'), the second character describing that the top gate was used (as shown by the 't') and the last characters showing it was device 7 that was used. 

There are two test types: 'I' for a current test and 'R' for a resistance test.
There are two gate types: 't' for top gate or 'b' for bottom gate operation.
Transistor number: can be anything, but is useful to differentaite tests from eachother.

### DataFile.file_path
The file location in your computer to the CSV file.

### Example
How to load the files 
```
test1 = tdv.DataFile(name='Ib7', path=r"Id-Vds var const Vbgs_n1.csv")
test2 = tdv.DataFile('It7', "Id-Vds var const Vtgs_n1.csv")
# be careful to make sure the string is properly formatted. Beware that '\' may be interpreted as an escape character in the file path
#   to prevent this, either use a raw string (eg. r'\') or use an escape character for backslash (eg. '\\')
```

## File: 
Turns a DataFile into a plottable object, but with limited plotting funcitonality.

### quick_plot3d(Zindex:int) 
Function to quickly plot the data contained in the File. 

### Example:
```
import TransistorDataVisualizer as tdv

test1 = tdv.DataFile(name='Ib7', path=r"Id-Vds var const Vbgs_n1.csv")

File1 = tdv.File(test1)
File1.quick_plot3d(Zindex = -1) 
# the selected Zindex selects what gets plotted on the Z axis based on the indices from the CSV file
```

## DataSet
Turns a DataFile into a useful plottable object and has more plotting functionality

### quick_plot3d(Zindex:int = -1)

```
test1 = tdv.DataFile('Ib7',r"Id-Vds var const Vbgs_n1.csv")
S1 = tdv.DataSet(test1)
S2 = tdv.DataSet(test2)

S1.quick_plot3d(-1) 
```

# DataBank
## The main feature of the tdv package

## The DataBank is used to store and plot multiple DataSets against eachother. 

### Adding/Removing DataSets to the DataBank
Use the .append() or .pop() methods

### print()
You can also show what is in your DataBank using its `.print()` function.

## Plotting

### quick_plot2d()

### quick_div_plot3d(Zindex, divSet, divIdx)

### quick_plot3d(Zindex=-1)

#### Example:
```
B = tdv.DataBank()

B.append(S1) # You can use the .append() and .pop() methods to add or remove DataSets from the DataBank
    
B.quick_plot3d(-1) # You can run use quick_plot3d() to visualize the data in 3d
        # to add connectors, toggle it by setting DataBank.connectors = True
        # to have labels automatically generated, toggle it with DataBank.autolabels = True
    
B.quick_plot2d('x', -1) # You can use the .quick_div2d() function to make a 2d plot of the DataBank

B.quick_div_plot3d(S2, -1) # You can compare performance across devices using the .qucik_div_plot3d() function 
```

### Domain Restriction
You can also restrict the domain that's being plotted on. The DataBank has a 'domain' attribute that can be varied (and reset).

#### Example:
```
B.domain # shows default domain
B.set_domain('x', [0, 5])
B.set_domain('y', [0, 3])
B.domain # shows updated domain

B.quick_plot3d()
B.quick_plot2d('x', -1)
B.quick_div_plot3d(S2, -1)

B.reset_domain()# You can reset the domain vis the reset function
B.domain # now the domain is back to its default settings
```



### Override
The databank will need its `override` attribute set to `True` in order to add DataSets of mismatching test type (for instance adding a 'Ib7' test to a DataBank containing a 'It7' test)

#### Example:
```# You can add more things too
B.append(S1)
B.append(S2)
# but this will give you a mismatching gate type error because we're adding two files of different test types
# we can override this (it may make the labels strange though)
B.override = True
B.append(S2)

B.quick_plot3d()
```