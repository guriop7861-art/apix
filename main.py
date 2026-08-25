from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import duckdb

app = FastAPI()

# In-memory DuckDB setup with caching & performance tweaks
con = duckdb.connect()
con.execute("INSTALL httpfs; LOAD httpfs;")
con.execute("SET enable_http_metadata_cache = true;")
con.execute("SET enable_object_cache = true;")
con.execute("SET http_keep_alive = true;")
con.execute("SET preserve_insertion_order = false;")

LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gateway - LIVE</title>
</head>
<body style="background:#050505; color:#00ffcc; font-family:monospace; text-align:center; padding-top:100px;">
    <h1>SYSTEM ONLINE</h1>
    <p>API Gateway is Active & Secured</p>
</body>
</html>
"""

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return JSONResponse(
            status_code=404,
            content={"status": "rejected", "message": "Invalid endpoint"}
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.get("/", response_class=HTMLResponse)
def root_landing_page():
    return HTMLResponse(content=LANDING_PAGE_HTML, status_code=200)

@app.get("/FetchData")
def fetch_data(Number: str = Query(None)):
    # Strict 10-digit validation
    if not Number or not Number.isdigit() or len(Number) != 10:
        return JSONResponse(
            status_code=400,
            content={"status": "rejected", "message": "Please enter a valid 10-digit number"}
        )
    
    last_digit = Number[-1]
    
    primary_url = f"https://huggingface.co/buckets/CutehackX/hitek-data-bucket/resolve/final_master_shard_{last_digit}.parquet?download=true"
    alt_url = f"https://huggingface.co/buckets/CutehackX/hitek-data-bucket/resolve/alt_master_shard_{last_digit}.parquet?download=true"
    third_url = "https://huggingface.co/datasets/Kzr0xx/icrm-hitek-full-db-mixed/resolve/main/idx_aadhar.0.parquet?download=true"
    
    try:
        query = f"""
            SELECT *, 'Primary_DB' AS _source 
            FROM read_parquet('{primary_url}') 
            WHERE mobile = $1
            
            UNION ALL BY NAME
            
            SELECT *, 'Alt_DB' AS _source 
            FROM read_parquet('{alt_url}') 
            WHERE mobile = $1
            
            UNION ALL BY NAME
            
            SELECT *, 'Third_DB' AS _source 
            FROM read_parquet('{third_url}') 
            WHERE "phoneNumber" = $1 OR "otherNumber" = $1
        """
        
        cursor = con.cursor()
        raw_results = cursor.execute(query, [Number]).fetchall()
        col_names = [desc[0] for desc in cursor.description]
        
        all_records = []
        for row in raw_results:
            row_dict = {col: val for col, val in zip(col_names, row) if val is not None}
            all_records.append(row_dict)
        
        if not all_records:
            return JSONResponse(
                status_code=404,
                content={"status": "not_found", "phone": Number, "message": "No data found for this number"}
            )
            
        return {
            "status": "success",
            "phone": Number,
            "total_records": len(all_records),
            "records": all_records
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Database processing error: {str(e)}"}
        )
        
