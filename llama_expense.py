# ============================================================
# TAX EXPENSE CATEGORIZER - YAML VERSION
# ============================================================
# This script categorizes business expenses using LLMs for tax purposes
import pandas as pd
import os
import json
from rich import print
from langchain_core.output_parsers import JsonOutputParser
from langchain_ollama import ChatOllama
from dotenv import load_dotenv
import time
from langchain_core.prompts import load_prompt

load_dotenv(".env")


# ============================================================
# 1. CONFIGURATION SECTION
# ============================================================
# File paths
DATA_DIR = "data"
INPUT_EXCEL_PATH = os.path.join(DATA_DIR, "test_input.csv")
OUTPUT_CSV_PATH = os.path.join(DATA_DIR, "categorized_expenses.csv")
PROMPT_FILE_PATH = "prompt.yaml"

# Default values
DEFAULT_CATEGORY = "Unknown"
DEFAULT_DEDUCTIBLE = False
ERROR_CATEGORY = "Error"
DEFAULT_JUSTIFICATION = "No justification provided by LLM"
DATE_FORMAT = "%Y-%m-%d"

# LLM Configuration
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4-mini")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "phi4")
# OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma3:12b")


# ============================================================
# 2. PROMPT LOADING FUNCTION
# ============================================================
def load_prompt_from_file(file_path):
    """Loads the prompt from a YAML file."""


# ============================================================
# 3. UTILITY FUNCTIONS
# ============================================================
def setup_directories():
    """Ensure necessary directories exist."""


def parse_date(date_value):
    """Parse date value to a consistent format. Will raise error on failure."""


def direct_json_loads(json_string):
    """Directly parses a JSON string, raising errors on failure."""


# ============================================================
# 4. DATA HANDLING FUNCTIONS
# ============================================================
def read_expense_data(input_path):
    """Read expense data from CSV file. Will raise error on failure."""


def save_expense_data(df, output_path):
    """Save processed expense data to CSV file."""


# ============================================================
# 5. LLM SETUP FUNCTIONS
# ============================================================
def initialize_llm(ChatOllama):
    """Initialize the LLM with appropriate settings."""


# Modified to use the langchain prompt object directly
def create_processing_chain(llm, prompt):
    """Create the Langchain processing chain with prompt template and JSON output parsing."""


# ============================================================
# 6. EXPENSE PROCESSING FUNCTIONS
# ============================================================
def process_single_expense(row, processing_chain, index, total_rows):
    """
    Process a single expense row using the LLM chain.
    Will raise errors if LLM call or JSON parsing fails.
    """


def process_expenses(input_path, output_path, processing_chain):
    """
    Reads expenses from a CSV file, categorizes them using LLM,
    adds justification, and saves the results to a new CSV file.
    Will halt on the first error encountered during processing.
    """


# ============================================================
# 7. MAIN FUNCTION
# ============================================================
def main():
    """Main function to run the expense categorization process."""
    start_time = time.time()
    print("\n==== TAX EXPENSE CATEGORIZER (YAML EDITION) ====")

    # Step 1: Setup environment
    setup_directories()

    # Step 2: Load the prompt from the YAML file
    expense_categorization_prompt = load_prompt_from_file(PROMPT_FILE_PATH)

    # Step 3: Initialize language model
    llm = initialize_llm(ChatOllama)

    # Step 4: Create processing chain using the loaded prompt object
    processing_chain = create_processing_chain(llm, expense_categorization_prompt)

    # Step 5: Process expenses - Script will handle errors per row
    process_expenses(INPUT_EXCEL_PATH, OUTPUT_CSV_PATH, processing_chain)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"\nExecution time: {elapsed_time:.2f} seconds")
    print("\n✅ Process completed!")


if __name__ == "__main__":
    main()
