1. Reading a file
```python
with open("logs.txt", "r") as file:
    for line in file:
        print(line.strip())
```

2. Reads the entire file as one string.

```python
with open("logs.txt", "r") as file:
    content = file.read()

print(content)
```

3. Reads one line at a time.

```python
with open("logs.txt", "r") as file:
    line1 = file.readline()
    line2 = file.readline()

print(line1.strip())
print(line2.strip())
```

4. write

```python
with open("output.txt", "w") as file:
    file.write("Hello Deepjyot\n")
    file.write("This is a test file\n")
```

5. append


```python

with open("output.text", "a") as file:
    file.write("hello how are you?")
    file.write("I am doing good, how are you?")

```

6. Dictionary reader

```python
import csv

with open("users.csv", "r") as file:
    reader = csv.DictReader(file)

    for row in reader:
        print(row["name"], row["role"])
```