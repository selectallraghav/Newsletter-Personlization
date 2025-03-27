import os
import datetime
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine
from jinja2 import Environment, FileSystemLoader
from fastapi.responses import JSONResponse

# FastAPI Application Setup
app = FastAPI(title="Newsletter Generation API")

# Database Configuration
DB_URL = "postgresql://postgres:Raghav123@localhost:5432/postgres"
engine = create_engine(DB_URL)

# Pydantic Model for Request Validation
class CustomerRequest(BaseModel):
    customer_id: int

# Reuse existing functions from your original script
def load_customer_data():
    """Loads customer demographics and model output data, merging them on Customer_ID."""
    demographics_query = "SELECT * FROM \"CustomerDemographics\""
    model_output_query = "SELECT * FROM \"ModelOutputData\""
    
    demographics_df = pd.read_sql(demographics_query, engine)
    model_output_df = pd.read_sql(model_output_query, engine)
    
    # Filter customers where customer_response == 1
    model_output_df = model_output_df[model_output_df['customer_response_in_binary'] == 1]
    
    # Merge data on Customer_ID
    merged_df = pd.merge(model_output_df, demographics_df, on='Customer_ID', how='inner')
    
    # Standardize marital status
    merged_df['Marital_Status'] = merged_df['Marital_Status'].apply(lambda x: 'Married' if x == 'Married' else 'Single')
    
    return merged_df

def load_merged_data():
    """Load merged data containing email headers and bodies from PostgreSQL."""
    merged_data_query = "SELECT * FROM \"MergedData\""
    merged_data_df = pd.read_sql(merged_data_query, engine)
    return merged_data_df

def get_local_file(file_path):
    """Fetch files from the local system."""
    if os.path.exists(file_path):
        return file_path
    return None

def get_loan_image(gender, marital_status, loan_type):
    """Returns the appropriate loan image based on gender, marital status, and loan type."""
    mapping = {
        "auto": {
            "Married": "FamilyAutoLoan.png",
            "Male": "MaleAutoLoan.png",
            "Female": "FemaleAutoLoan.png"
        },
        "home": {
            "Married": "FamilyHomeLoan.png",
            "Male": "MaleHomeLoan.png",
            "Female": "FemaleHomeLoan.png"
        }
    }
    loan_type = loan_type.lower()
    marital_status = "Married" if marital_status == "Married" else "Single"

    image_name = mapping.get(loan_type, {}).get("Married" if marital_status == "Married" else gender, "Loan-Approved.png")
    image_path = f"{image_name}"
    return get_local_file(image_path) if os.path.exists(image_path) else None

def generate_loan_letter(customer_data, template_path):
    """Generates a home loan letter using a template and customer data."""
    try:
        template_dir = os.path.dirname(template_path)
        template_file = os.path.basename(template_path)
        env = Environment(loader=FileSystemLoader(template_dir))
        template = env.get_template(template_file)
        html_letter = template.render(customer_data)
        return html_letter
    except Exception as e:
        return f"Error rendering template: {e}"


@app.post("/generate_newsletter")
async def generate_newsletter(request: CustomerRequest):
    customer_df = load_customer_data()
    merged_data_df = load_merged_data()

    customer_data_row = customer_df[customer_df['Customer_ID'] == request.customer_id]

    if customer_data_row.empty:
        raise HTTPException(status_code=404, detail=f"No data found for Customer ID {request.customer_id}")

    row = customer_data_row.iloc[0]

    email_data = merged_data_df[merged_data_df['Customer_ID'] == request.customer_id]
    email_header = email_data.iloc[0]['Header'] if not email_data.empty else f"Loan Offer for {row['Full_Name']}"
    email_body = email_data.iloc[0]['Email Body'] if not email_data.empty else f"Dear {row['Full_Name']},\n\nWe are pleased to offer you a loan..."

    gender = row['Gender']
    marital_status = row['Marital_Status']
    loan_type = "home"
    loan_image_path = get_loan_image(gender, marital_status, loan_type)
    bank_logo_path = get_local_file("/Users/raghav/Downloads/ally_bank_image.jpeg")

    customer_data = {
        "Customer_ID": request.customer_id,
        "loan_image_path": loan_image_path,
        "bank_logo_path": bank_logo_path,
        "bank_name": "Ally Bank",
        "bank_street": "123 Main St",
        "bank_city": "Anytown",
        "bank_state": "CA",
        "bank_zip": "91234",
        "current_date": datetime.date.today().strftime("%B %d, %Y"),
        "customer_name": row['Full_Name'],
        "loan_amount": "$25,000",
        "interest_rate": "4.9%",
        "loan_term": "60 months",
        "monthly_payment": "$470",
        "bank_phone": "555-1212",
        "bank_email": "info@Ally.com",
        "bank_website": "www.Ally.com",
        "email_body": email_body,
        "email_header": email_header
    }

    html_output = generate_loan_letter(customer_data, "/Users/raghav/Downloads/auto_loan_template.html")

    if "Error:" in html_output:
        raise HTTPException(status_code=500, detail=f"Error generating newsletter: {html_output}")

    # Save to local file (optional)
    output_dir = "generated_template"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"generated_loan_offer_{request.customer_id}.html")

    with open(output_path, "w") as f:
        f.write(html_output)

    # ✅ Return the content to Power Automate
    return JSONResponse(content={
        "status": "success",
        "customer_id": request.customer_id,
        "file_name": f"Generated_Newsletter_{request.customer_id}.html",
        "newsletter_html": html_output
    })


# Optional: Health check endpoint
@app.get("/")
async def health_check():
    return {"status": "API is running"}