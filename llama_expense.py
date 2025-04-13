# ============================================================
# TAX EXPENSE CATEGORIZER - TUTORIAL VERSION
# ============================================================
# This script categorizes business expenses using LLMs for tax purposes
# Author: Your Name
# Date: April 2025

import pandas as pd
import os
import json
from rich import print
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# ============================================================
# 1. CONFIGURATION SECTION
# ============================================================

# File paths
DATA_DIR = "data"
INPUT_EXCEL_PATH = os.path.join(DATA_DIR, "test_input.csv")
OUTPUT_CSV_PATH = os.path.join(DATA_DIR, "categorized_expenses.csv")

# Default values
DEFAULT_CATEGORY = "Unknown"
DEFAULT_DEDUCTIBLE = False
ERROR_CATEGORY = "Error"
DEFAULT_JUSTIFICATION = "No justification provided by LLM"
DATE_FORMAT = "%Y-%m-%d"

# LLM Configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://eos-parkmour.local:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5")
# Alternative models (uncomment to use)
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")

# ============================================================
# 2. PROMPT TEMPLATE
# ============================================================

EXPENSE_CATEGORIZATION_PROMPT = """
You are an expert AI assistant specialized in US tax law concerning business expense deductions for Limited Liability Companies (LLCs).
Your primary task is to analyze potential business expenses, categorize them accurately, and determine their likely tax deductibility based on IRS guidelines.

**Core Principle:** For an expense to be deductible by a US LLC, it must be both **ordinary** AND **necessary** for carrying on the trade or business.
* **Ordinary:** Common and accepted in the LLC's specific trade or business.
* **Necessary:** Helpful and appropriate for the business. It doesn't have to be indispensable.

**Context for Analysis:**
* The expense details provided are for a US-based LLC.
* Assume the expense was incurred with a *potential* business purpose, BUT critically evaluate if the item itself suggests a **personal use** component or seems unrelated to common business activities.
* The expense must be **directly related** to the LLC's business activities. Expenses with a significant personal element are generally non-deductible or require allocation (which is outside this scope - mark as false if predominantly personal).
* Consider the **reasonableness** of the expense, although precise judgment is difficult without full context. Clearly excessive costs might be questioned by the IRS.

**Expense Details to Analyze:**
- Product Name: {product_name}
- Unit Price: {unit_price}
- Quantity: {quantity}
- Order Date: {order_date}

**Instructions:**

1.  **Analyze the Product/Service:** Based on the `product_name`, `unit_price`, and `quantity`, assess its likely use within a business context.
2.  **Categorize:** Assign the expense to *one* of the following standard business categories. If an item could fit multiple, choose the most specific or primary use.
    * Office Supplies & Software
    * Computer Hardware & Equipment
    * Professional Development & Education (Must relate to maintaining/improving skills for the *current* business)
    * Marketing & Advertising
    * Travel (Transportation, Lodging - Specify which, must be away from tax home overnight for lodging)
    * Business Meals (Subject to limitations, often 50% deductible, but mark `true` if a valid business meal occurred)
    * Utilities (For business property/home office)
    * Rent & Lease (For business property)
    * Subscriptions & Dues (Business-related publications, professional organizations)
    * Cost of Goods Sold (COGS) - Items for resale or direct materials/labor in producing goods/services for sale.
    * Repairs & Maintenance (For business property/equipment)
    * Insurance (Business-related policies)
    * Professional Services (Legal, Accounting, Consulting fees)
    * Bank Fees & Charges
    * Business Interest Expense
    * Taxes & Licenses (Business-related, not federal income tax)
    * Other Business Expense (Use sparingly for valid business costs not fitting elsewhere)
    * Potentially Personal / Non-Deductible (Items primarily for personal benefit, entertainment, commuting, certain clothing, political contributions, etc.)
3.  **Determine Deductibility (`is_deductible`):**
    * Set to `true` if the expense appears **ordinary and necessary** for the LLC's business based *solely* on the provided details and general business knowledge.
    * Set to `false` if the expense:
        * Seems primarily **personal** in nature (e.g., groceries, everyday clothing, personal hobbies, entertainment).
        * Is explicitly **non-deductible** by IRS rules (e.g., most entertainment expenses, political contributions, fines/penalties).
        * Is highly **ambiguous**, and a clear business connection isn't apparent from the product name (err on the side of caution).
        * Relates to starting a business but incurred *before* the business officially started operations (these are often capitalized startup costs, not immediate deductions - mark false for this initial pass).
4.  **Justify:** Provide a concise explanation for your category choice and deductibility assessment. Reference the "ordinary and necessary" standard and mention any specific considerations (e.g., "Likely deductible as software necessary for operations," or "Potentially personal, clothing not specific workwear, marked non-deductible"). Mention potential limitations like the 50% meal rule if applicable but keep the boolean based on whether it's a *qualifying* business expense at all.

**Output Format:**
Return your response ONLY as a valid JSON object with the following keys:
- "category": string (The determined expense category)
- "is_deductible": boolean (true or false based on the analysis above)
- "justification": string (Your brief reasoning connecting the item to business deductibility rules)
**Example Input Expense:**
Product Name: Business Lunch Meeting with Client XYZ
Unit Price: 85.50
Quantity: 1
Order Date: 2024-03-10

**Example JSON Output:**
{{
  "category": "Business Meals",
  "is_deductible": true,
  "justification": "Business meal with a client is ordinary and necessary for maintaining business relationships. Note: Typically subject to 50% limitation on deduction amount."
}}
"""

# ============================================================
# 3. UTILITY FUNCTIONS
# ============================================================


def setup_directories():
    """Ensure necessary directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"✓ Ensured data directory exists: {DATA_DIR}")


def parse_date(date_value):
    """Parse date value to a consistent format."""
    try:
        if isinstance(date_value, pd.Timestamp):
            return date_value.strftime(DATE_FORMAT)
        else:
            return pd.to_datetime(date_value).strftime(DATE_FORMAT)
    except Exception:
        return str(date_value)  # Fallback to string if parsing fails


def safe_json_loads(json_string):
    """Safely parses a JSON string, returning None on failure."""
    try:
        # Handle potential markdown code blocks around JSON
        if isinstance(json_string, str):
            if json_string.strip().startswith("```json"):
                json_string = json_string.strip()[7:-3].strip()
            elif json_string.strip().startswith("```"):
                json_string = json_string.strip()[3:-3].strip()
        # If it's already a dict (parsed by JsonOutputParser), return it directly
        if isinstance(json_string, dict):
            return json_string
        return json.loads(json_string)
    except json.JSONDecodeError:
        print(f"Warning: Failed to decode JSON: {json_string}")
        return None
    except Exception as e:
        print(f"Warning: An unexpected error occurred during JSON parsing: {e}")
        return None


# ============================================================
# 4. DATA HANDLING FUNCTIONS
# ============================================================


def read_expense_data(input_path):
    """Read expense data from CSV file."""
    try:
        df = pd.read_csv(input_path)
        print(f"✓ Successfully read {len(df)} rows from {input_path}")
        return df
    except FileNotFoundError:
        print(f"❌ Error: Input file not found at {input_path}")
        return None
    except Exception as e:
        print(f"❌ Error reading CSV file: {e}")
        return None


def save_expense_data(df, output_path):
    """Save processed expense data to CSV file."""
    try:
        df.to_csv(output_path, index=False)
        print(f"✓ Processing complete. Results saved to {output_path}")
        return True
    except Exception as e:
        print(f"❌ Error saving CSV file: {e}")
        return False


# ============================================================
# 5. LLM SETUP FUNCTIONS
# ============================================================


def import_llm_module():
    """Import the appropriate ChatOllama module."""
    try:
        from langchain_ollama import ChatOllama

        print("✓ Successfully imported ChatOllama from langchain_ollama.")
        return ChatOllama
    except ImportError:
        try:
            from langchain_community.chat_models import ChatOllama

            print("✓ Imported ChatOllama from langchain_community.chat_models.")
            print("Note: Consider updating Langchain packages for latest features.")
            return ChatOllama
        except ImportError:
            print("❌ Error: Could not import ChatOllama.")
            print(
                "Please install required packages: pip install pandas openpyxl langchain langchain-community langchain-ollama rich"
            )
            exit(1)


def initialize_llm(ChatOllama):
    """Initialize the LLM with appropriate settings."""
    try:
        llm = ChatOllama(
            model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, format="json", temperature=0.1
        )
        print(
            f"✓ Initialized ChatOllama with model '{OLLAMA_MODEL}' at {OLLAMA_BASE_URL}"
        )
        return llm
    except Exception as e:
        print(f"❌ Error initializing ChatOllama: {e}")
        print(
            f"Please ensure Ollama server is running at {OLLAMA_BASE_URL} and model '{OLLAMA_MODEL}' is available."
        )
        exit(1)


def create_processing_chain(llm):
    """Create the Langchain processing chain with prompt template and JSON output parsing."""
    prompt_template = ChatPromptTemplate.from_template(EXPENSE_CATEGORIZATION_PROMPT)
    chain = prompt_template | llm | JsonOutputParser()
    print("✓ Created LLM processing chain with prompt template and JSON parser")
    return chain


# ============================================================
# 6. EXPENSE PROCESSING FUNCTIONS
# ============================================================


def process_single_expense(row, processing_chain, index, total_rows):
    """Process a single expense row using the LLM chain."""
    # Extract relevant data for the prompt
    product_name = row.get("Product Name", "N/A")
    unit_price = row.get("Unit Price", 0.0)
    quantity = row.get("Quantity", 1)
    order_date = parse_date(row.get("Order Date", "N/A"))

    # Skip rows with missing essential data
    if product_name == "N/A":
        print(f"⚠️ Skipping row {index + 1} due to missing 'Product Name'.")
        return DEFAULT_CATEGORY, DEFAULT_DEDUCTIBLE, "Missing product information"

    try:
        # Process the expense through the LLM chain
        result_raw = processing_chain.invoke(
            {
                "product_name": product_name,
                "unit_price": unit_price,
                "quantity": quantity,
                "order_date": order_date,
            }
        )

        # Safely parse the JSON output
        result = safe_json_loads(result_raw)
        if result:  # Check if parsing was successful
            category = result.get("category", DEFAULT_CATEGORY)
            is_deductible = result.get("is_deductible", DEFAULT_DEDUCTIBLE)
            justification = result.get("justification", DEFAULT_JUSTIFICATION)

            # Log results
            print(f"  📦 Product: {product_name}")
            print(f"  🏷️ Categorized as: {category}")
            print(f"  💰 Deductible: {is_deductible}")
            print(f"  📝 Justification: {justification}")

            return category, is_deductible, justification
        else:
            # Handle JSON parsing failure
            print(f"  ❌ Error: Failed to parse LLM response for row {index + 1}")
            return ERROR_CATEGORY, DEFAULT_DEDUCTIBLE, "LLM response parsing error"
    except Exception as e:
        print(f"❌ Error processing row {index + 1}: {e}")
        return ERROR_CATEGORY, DEFAULT_DEDUCTIBLE, f"Processing error: {str(e)}"


def process_expenses(input_path, output_path, processing_chain):
    """
    Reads expenses from a CSV file, categorizes them using LLM,
    adds justification, and saves the results to a new CSV file.
    """
    print("\n🚀 Starting expense processing...")
    print(f"📂 Reading input CSV file: {input_path}")

    # Read the input data
    df = read_expense_data(input_path)
    if df is None:
        return

    # Prepare lists to store results
    categories = []
    deductibility = []
    justifications = []

    # Process each expense row
    for index, row in df.iterrows():
        print(f"\n⏳ Processing row {index + 1}/{len(df)}...")
        category, is_deductible, justification = process_single_expense(
            row, processing_chain, index, len(df)
        )
        categories.append(category)
        deductibility.append(is_deductible)
        justifications.append(justification)

    # Add the analysis results to the dataframe
    df["Category"] = categories
    df["Is Deductible"] = deductibility
    df["Justification"] = justifications

    # Save the results
    print(f"\n💾 Saving results to {output_path}")
    save_expense_data(df, output_path)


# ============================================================
# 7. MAIN FUNCTION
# ============================================================


def main():
    """Main function to run the expense categorization process."""
    print("\n==== TAX EXPENSE CATEGORIZER ====")

    # Step 1: Setup environment
    setup_directories()

    # Step 2: Initialize language model
    ChatOllama = import_llm_module()
    llm = initialize_llm(ChatOllama)

    # Step 3: Create processing chain
    processing_chain = create_processing_chain(llm)

    # Step 4: Process expenses
    process_expenses(INPUT_EXCEL_PATH, OUTPUT_CSV_PATH, processing_chain)

    print("\n✅ Process completed successfully!")


# ============================================================
# 8. SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
