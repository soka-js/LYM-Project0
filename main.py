from logic import check_file

def main():
    filename = input("Enter the name of the file to upload (ej: test_robot.txt): ").strip()
    result = check_file(filename)
    print(result)

if __name__ == '__main__':
    main()
