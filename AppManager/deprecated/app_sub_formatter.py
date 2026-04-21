'''
'''
import re
import os


def useRegex(input_text):
    pattern = re.compile(
        r"file\s+([A-Za-z0-9]+(_[A-Za-z0-9]+)+)\.[a-zA-Z]+\s+", re.IGNORECASE)
    return pattern.match(input_text)


def getUserSelectedFile(directory):
    print("=====================================================================================")
    print("Select a file from the list below by entering the index to the left of the file name:")
    files = [file for file in directory if file.endswith(".substitutions")]
    for i in range(len(files)):
        print(str(i) + ": " + files[i])
    validated = False
    selectFileIndex = None
    attempts = 0
    if len(files) < 1:
        print("No files found. Exiting program.")
        exit()
    while not validated and len(files) > 0:
        try:
            selectFileIndex = int(
                input("Enter the index of the file you want to format: "))
            if selectFileIndex < 0 or selectFileIndex >= len(files):
                raise ValueError
            validated = True
        except ValueError:
            attempts += 1
            if attempts >= 3:
                print("Too many invalid attempts. Exiting program.")
                exit()
            print("Invalid index. Please try again.")
    print("======================================================================================")
    return files[int(selectFileIndex)]

def stripWhiteSpace(text):
    lst = text.split('"')
    for i, item in enumerate(lst):
        if not i % 2:
            lst[i] = re.sub("\s+", "", item)
    return '"'.join(lst)

def main():
    ''' 
        Explanation of code:

    '''
    # Get the current working directory
    cwd = os.getcwd()
    directory = os.listdir(cwd)
    # Get the file name from the user
    fileName = getUserSelectedFile(directory)
    # Create a new file
    newFile = ""
    # Keep track of added comments
    commentsAdded = {}
    
    COMMA_MATCHER = re.compile(r",(?=(?:[^\"']*[\"'][^\"']*[\"'])*[^\"']*$)")

    # Read the file
    file = open(fileName, 'r')
    lines = file.readlines()
    
    # Read the file line by line
    for index, line in enumerate(lines):
        if re.search(r'^#', lines[index]):
            # print("Comment found: " + line)
            if not commentsAdded.get(index):
                commentsAdded[index] = True
                newFile += line

        elif re.search(r'^file\s+[ A-Za-z0-9_]+\.[a-zA-Z]+', lines[index]):
            # Initialising variables
            newRecord = re.search(r'^file\s+[ A-Za-z0-9_]+\.[a-zA-Z]+', lines[index]).group(0)
            header = []
            rows = []
            columnWidths = {}
            
            for j in range(index + 1, len(lines)):
                # If the line is a "}", then we have reached the end of the current record, so break out of the loop
                if re.match(r'}', lines[j]):
                    break

                # If the line contains 'pattern'
                elif re.match(r'\s+pattern\s+', lines[j]):
                    # Split the line into a list of columns where between { and } is a column, split by comman unless its between " and "
                    
                    # Split the line into a list of column names by splitting by comma except when the comma is between " and "
                    header = lines[j].split('{')[1].split('}')[0]
                    header = COMMA_MATCHER.split(header)
                    header = [stripWhiteSpace(item) for item in header] 
                    # Loop through the header columns
                    for k in range(0, len(header)):

                        # If the column is not in the dictionary, add it
                        if not columnWidths.get(k):
                            columnWidths[k] = len(header[k])

                        # Find the longest column and set the column width
                        elif len(header[k]) > columnWidths[k]:
                            columnWidths[k] = len(header[k])

                # If the line is a "{", then we have reached the start of the rows
                elif re.match(r'\s+{', lines[j]):

                    
                    # Split the row into columns using , as a delimiter except when the comma is between " and "                 
                    row = lines[j].split('{')[1].split('}')[0]
                    row = COMMA_MATCHER.split(row)

                    # Call the stripWhiteSpace function on each column in the row
                    row = [stripWhiteSpace(item) for item in row] 
                    
                    
                    # row = [item.replace(' ', '') for item in row]

                    # Add the row to the rows list
                    rows.append(row)

                    # Loop through the row columns
                    for l in range(0, len(row)):

                        # If the column is not in the dictionary, add it
                        if not columnWidths.get(l):
                            columnWidths[l] = len(row[l])

                        # Find the longest column and set the column width
                        elif len(row[l]) > columnWidths[l]:
                            columnWidths[l] = len(row[l])

                # If the line is a comment, add it to the new file
                elif re.match(r'^#', lines[j]) and not commentsAdded.get(lines[j]):
                    commentsAdded[j] = True
                    rows.append(lines[j])

            newRecord += "\n"
            newRecord += "{\n"
            newRecord += "    pattern   { "

            for m in range(0, len(header)):
                if m == len(header) - 1:
                    newRecord += header[m] + " " * \
                        (columnWidths[m] - len(header[m]) + 2) + " }\n"
                else:
                    newRecord += header[m] + "," + " " * \
                        (columnWidths[m] - len(header[m]) + 2)

            for p in range(0, len(rows)):
                if re.match(r'^#', rows[p][0]):
                    newRecord += str(rows[p])
                else:
                    newRecord += "              { "
                    for q in range(0, len(rows[p])):
                        if q == len(rows[p]) - 1:
                            newRecord += rows[p][q] + " " * \
                                (columnWidths[q] -
                                 len(rows[p][q]) + 2) + " }\n"
                        else:
                            newRecord += rows[p][q] + "," + " " * \
                                (columnWidths[q] - len(rows[p][q]) + 2)
            print("cols", columnWidths)
            # Add the closing bracket
            newRecord += '}\n'

            newFile += newRecord
    newFile += '#\n'
    # Write the new file
    newFileName = fileName.split('.')[0] + '.substitutions'
    # Let the user know what the new file name is and where is has been saved
    print("======================================================================================")
    print("The new file has been saved as " + newFileName)

    # Create the new file
    with open(newFileName, 'w') as f:
        f.write(newFile)
    # print(newFile)


if __name__ == '__main__':
    main()
