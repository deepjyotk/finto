import csv

with open("users.csv", "r") as file:
    reader = csv.DictReader(file)


    print("reader type is: ", type(reader))

    for row in reader:
        print(row["name"], row["role"])