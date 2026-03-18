import pyodbc

conn_str = "Driver={ODBC Driver 17 for SQL Server};Server=localhost,1433;Database=EBR_Template;UID=traksys_app;PWD=TrakSYS99!;TrustServerCertificate=yes"

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Cast datetime to string in SQL
cursor.execute("""
    SELECT TOP 5 
        ID, 
        Name,
        CONVERT(nvarchar(30), StartDateTime, 126) as StartDateTime_str,
        CONVERT(nvarchar(30), EndDateTime, 126) as EndDateTime_str
    FROM tBatch
""")

rows = cursor.fetchall()

print("\n=== Results with SQL CAST ===")
for row in rows:
    print(f"ID: {row[0]}, Name: {row[1]}")
    print(f"  Start: {row[2]} ({type(row[2])})")
    print(f"  End: {row[3]} ({type(row[3])})")
    print("-" * 40)

conn.close()