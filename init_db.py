import mysql.connector

def init_db():
    try:
        # Prompt user for credentials if needed, or assume root/root as per Function.cs
        conn = mysql.connector.connect(host='localhost', user='root', password='root')
        cur = conn.cursor()
        
        print("Creating database 'fceol' if it doesn't exist...")
        cur.execute('CREATE DATABASE IF NOT EXISTS fceol')
        cur.execute('USE fceol')

        print("Creating settingmaster table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS settingmaster (
            pno VARCHAR(50) PRIMARY KEY,
            pname VARCHAR(100),
            cname VARCHAR(100),
            mname VARCHAR(100),
            vendorcode VARCHAR(50),
            alc VARCHAR(50),
            eocode VARCHAR(50),
            chsel VARCHAR(10),
            lblsel VARCHAR(100),
            machine VARCHAR(50)
        )''')

        print("Creating settingspec table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS settingspec (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pno VARCHAR(50),
            testname VARCHAR(100),
            chsel VARCHAR(10),
            appvol VARCHAR(20),
            testtime VARCHAR(20),
            min VARCHAR(20),
            max VARCHAR(20),
            FOREIGN KEY (pno) REFERENCES settingmaster(pno) ON DELETE CASCADE
        )''')

        print("Creating testmaster table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS testmaster (
            id INT AUTO_INCREMENT PRIMARY KEY,
            pno VARCHAR(50),
            pname VARCHAR(100),
            model VARCHAR(100),
            alc VARCHAR(50),
            channel VARCHAR(10),
            lotno VARCHAR(100) UNIQUE,
            date VARCHAR(20),
            time VARCHAR(20),
            empcode VARCHAR(50),
            result VARCHAR(20),
            scanresult VARCHAR(20),
            machine VARCHAR(50)
        )''')

        print("Creating testresult table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS testresult (
            id INT AUTO_INCREMENT PRIMARY KEY,
            lotno VARCHAR(100),
            channel VARCHAR(10),
            ir_volts VARCHAR(50),
            ir_resistance VARCHAR(50),
            ir_current VARCHAR(50),
            ir_result VARCHAR(50),
            acw_volts VARCHAR(50),
            acw_current VARCHAR(50),
            acw_result VARCHAR(50),
            contact_result VARCHAR(50)
        )''')

        print("Creating admin table...")
        cur.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            eno VARCHAR(50) PRIMARY KEY,
            ename VARCHAR(100),
            pwd VARCHAR(100),
            desig VARCHAR(100),
            dept VARCHAR(100)
        )''')
        
        print("Inserting default 'nice' admin user...")
        cur.execute('''
        INSERT IGNORE INTO admin (eno, ename, pwd, desig, dept) 
        VALUES ('nice', 'System Admin', 'nice1234', 'Administrator', 'IT')
        ''')

        conn.commit()
        print('✅ Database and all tables initialized successfully.')

    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
        print("Please ensure MySQL is running on localhost and the user 'root' with password 'root' exists.")
    finally:
        if 'cur' in locals(): cur.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    init_db()
