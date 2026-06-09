import argparse
import re
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.comments import Comment
from pathlib import Path

def parse_markdown(md_file):
    """Parse markdown file and extract test cases."""
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    test_cases = []
    
    # Split by generic test case ID pattern (PREFIX-###)
    pattern = r'#### ([A-Z0-9]+(?:-[A-Z0-9]+)*-\d{3}): (.+?)\n'
    matches = list(re.finditer(pattern, content))
    
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        
        test_block = content[start:end]
        
        test_id = match.group(1)
        title = match.group(2).strip()
        
        # Extract sections
        objective = extract_section(test_block, 'Objective')
        prerequisites = extract_section(test_block, 'Prerequisites')
        test_steps = extract_section(test_block, 'Test Steps')
        expected_results = extract_section(test_block, 'Expected Results')
        acceptance_criteria = extract_section(test_block, 'Acceptance Criteria')
        
        test_cases.append({
            'ID': test_id,
            'Title': title,
            'Objective': objective,
            'Prerequisites': prerequisites,
            'Test Steps': test_steps,
            'Expected Results': expected_results,
            'Acceptance Criteria': acceptance_criteria
        })
    
    return test_cases

def extract_section(text, section_name):
    """Extract content from a named section."""
    pattern = rf'\*\*{section_name}:\*?\*?\n(.+?)(?=\n\n|\*\*|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        # Clean up code blocks and formatting
        content = re.sub(r'```[\s\S]*?```', '', content)
        content = re.sub(r'\n\n+', ' | ', content)
        content = content.strip()
        return content
    return ''

def create_excel(test_cases, output_file):
    """Create Excel workbook from test cases."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Cases"
    
    # Define styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    
    cell_alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Set column widths
    columns = ['ID', 'Title', 'Objective', 'Prerequisites', 'Test Steps', 
               'Expected Results', 'Acceptance Criteria']
    col_widths = [15, 30, 40, 35, 40, 40, 40]
    
    # Column comments in Chinese
    col_comments = {
        'ID': '测试用例编号\n(如PCIE6-US-001)',
        'Title': '测试用例标题\n简要描述测试目的',
        'Objective': '测试目标\n详细说明测试需要验证的内容',
        'Prerequisites': '前置条件\n测试前需满足的系统要求',
        'Test Steps': '测试步骤\n详细的测试执行步骤和命令',
        'Expected Results': '预期结果\n测试正常执行时的预期输出',
        'Acceptance Criteria': '验收标准\n判断测试通过的量化标准'
    }
    
    for col_idx, (col_name, width) in enumerate(zip(columns, col_widths), 1):
        ws.column_dimensions[chr(64 + col_idx)].width = width
    
    # Write headers
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.value = col_name
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = border
        
        # Add Chinese comments to header cells
        comment = Comment(col_comments[col_name], "注释")
        comment.width = 300
        comment.height = 80
        cell.comment = comment
    
    # Write data
    for row_idx, test_case in enumerate(test_cases, 2):
        for col_idx, col_name in enumerate(columns, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.value = test_case.get(col_name, '')
            cell.alignment = cell_alignment
            cell.border = border
    
    # Set row height for header
    ws.row_dimensions[1].height = 30
    
    # Auto-fit row heights for data
    for row_idx in range(2, len(test_cases) + 2):
        ws.row_dimensions[row_idx].height = 60
    
    wb.save(output_file)
    print(f"✓ Excel file created: {output_file}")

def main():
    workspace_root = Path(__file__).parent.parent
    parser = argparse.ArgumentParser(description="Convert structured test case markdown into Excel.")
    parser.add_argument("--input", default=str(workspace_root / "docs" / "PCIE6_TEST_CASES.md"))
    parser.add_argument("--output", default=str(workspace_root / "docs" / "PCIE6_TEST_CASES.xlsx"))
    args = parser.parse_args()

    md_file = Path(args.input)
    output_file = Path(args.output)
    
    print(f"Reading: {md_file}")
    test_cases = parse_markdown(md_file)
    print(f"Parsed {len(test_cases)} test cases")
    
    print(f"Creating Excel file: {output_file}")
    create_excel(test_cases, output_file)

if __name__ == "__main__":
    main()
