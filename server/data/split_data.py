from pypdf import PdfReader, PdfWriter
import os

def process_pdf(input_path, output_dir):
    reader = PdfReader(input_path)
    
    # 출력 파일을 저장할 폴더 생성
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # 2페이지 단위로 건너뛰며 반복 (0, 2, 4, ... 18)
    for i in range(0, len(reader.pages), 2):
        writer = PdfWriter()
        
        # 현재 그룹의 2페이지를 각각 처리
        for j in range(2):
            if i + j < len(reader.pages):
                page = reader.pages[i + j]
                # 시계 반대 방향으로 90도 회전 (시계 방향 270도와 동일)
                page.rotate(-90) 
                writer.add_page(page)
        
        # 1번부터 10번까지 순차적으로 파일명 지정 및 저장
        output_filename = os.path.join(output_dir, f"split_document_{i//2 + 1}.pdf")
        with open(output_filename, "wb") as f:
            writer.write(f)
            
    print("PDF 회전 및 분할 작업이 완료되었습니다!")

# 실제 사용하는 파일명과 폴더명으로 변경해서 실행
process_pdf("캡스톤 손글씨.pdf", "splited_data")