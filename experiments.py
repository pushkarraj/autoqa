import pdfplumber
from langchain_openai import ChatOpenAI
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain.prompts import PromptTemplate
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService, Service
from selenium.webdriver.chrome.options import Options
import os
import json
import PyPDF2
from docx import Document
import pytest
from dotenv import load_dotenv

from utils import load_yaml_config

load_dotenv()


script_dir = os.getcwd()
prompt_config = load_yaml_config(os.path.join(script_dir, 'prompt.yaml'))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "http://3.83.24.72:8000/"  # Replace with the actual base URL

# Initialize LLM (e.g., OpenAI GPT)
llm = ChatOpenAI(model="gpt-4", openai_api_key=OPENAI_API_KEY, temperature=0.2)

# Step 1: Parse and Analyze the BRD
def parse_brd(file_path):
    if file_path.endswith('.docx'):
        # Extract text from .docx file
        document = Document(file_path)
        content = "\n".join([para.text for para in document.paragraphs])
    elif file_path.endswith('.pdf'):
        # Extract text from .pdf file
        content = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                content += page.extract_text() + "\n"
    else:
        raise ValueError("Unsupported file format. Use .docx or .pdf files.")
    return content

def analyze_requirements(brd_text):
    prompt = PromptTemplate.from_template(prompt_config['feature_prompt'])
    response = llm.invoke(prompt.format(text=brd_text))
    return json.loads(response.content)


# Step 2: Inspect Webpage and Map Requirements to Web Elements
def inspect_webpage(url, feature_requirements):
    """Uses Selenium to inspect a webpage and map features to web elements."""
    chrome_options = Options()
    driver = webdriver.Chrome(service=Service(), options=chrome_options)
    driver.get(url)

    element_mappings = {}
    for feature, requirement in feature_requirements.items():
        try:
            # Example: Find a button by its text
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{requirement}')]")
            ))
            element_mappings[feature] = {
                "xpath": element.get_attribute("outerHTML"),
                "description": requirement
            }
        except Exception as e:
            element_mappings[feature] = {"error": str(e)}

    driver.quit()
    return element_mappings


# Step 3: Automate Test Case Generation
def generate_test_cases(feature_requirements, element_mappings):
    """Generates Selenium-based test scripts for each feature."""
    test_cases = {}
    for feature, details in feature_requirements.items():
        element_xpath = element_mappings.get(feature, {}).get("xpath")
        if not element_xpath:
            continue

        test_script = f"""
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

@pytest.fixture
def driver():
    driver = webdriver.Chrome()
    yield driver
    driver.quit()

def test_{feature.replace(' ', '_')}():
    driver.get("your_test_url")
    element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "{element_xpath}"))
    )
    assert element is not None
"""
        test_cases[feature] = test_script
    return test_cases


# Step 4: Execute Tests and Generate Reports
def execute_tests(test_cases):
    """Executes the generated test cases and captures results."""
    results = {}
    for feature, script in test_cases.items():
        test_file = f"tests/test_{feature.replace(' ', '_')}.py"
        with open(test_file, "w") as f:
            f.write(script)

        try:
            pytest_result = pytest.main([test_file, "--maxfail=1", "--disable-warnings"])
            results[feature] = "pass" if pytest_result == 0 else "fail"
        except Exception as e:
            results[feature] = f"error: {str(e)}"

    return results


def generate_report(test_results, output_path="report.json"):
    """Generates a report summarizing the test results."""
    with open(output_path, "w") as f:
        json.dump(test_results, f, indent=4)
    print(f"Report saved to {output_path}")


# Example Execution
if __name__ == "__main__":
    print("Parse and Analyze BRD")
    brd_text = parse_brd("BRD - HRMS.pdf")
    feature_requirements = analyze_requirements(brd_text)
    print(feature_requirements)

    # Step 2: Inspect Webpage
    url = BASE_URL
    element_mappings = inspect_webpage(url, feature_requirements)

    # Step 3: Generate Test Cases
    test_cases = generate_test_cases(feature_requirements, element_mappings)

    # Step 4: Execute Tests and Generate Reports
    test_results = execute_tests(test_cases)
    generate_report(test_results)
