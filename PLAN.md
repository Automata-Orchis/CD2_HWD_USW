# Plan

`D:\CapstoneDesign2\project_gamma`에서 이루어질 모든 작업에 대한 계획이 작성되어 있다. 이를 기반으로 모든 작업이 진행되며, 작업의 진행 상황에 따라 내용이 수정될 수 있다. 

## 1. 목표에 대하여

**VLM을 활용하여 한글 손글씨가 작성된 문서로부터 손글씨를 정확히 인식하여 Exel 등의 결과물을 생성하라.**

목표에 대한 참고 사항은 아래와 같다.
- 보안을 위해 인터넷이 차단된 폐쇄망 환경에서의 오픈소스 모델 활용을 가정한다. 
- `Jupyter hub`를 통해 서버의 `CPU`와 `GPU`를 사용해야 한다. 우선되는 것은 `GPU`다.
- 모델의 추론이 정상적으로 이루어지는 것이 목적이다. 모델의 학습은 계획에 없다. 
- 여러 오픈소스 모델의 예측과 그 정확도 등의 테스트를 진행, 그 결과는 `Database`에 저장되어야 한다. 

## 2. 작업 방향에 대하여

**이 작업은 모델이 문서를 정확히 인식하여, 사람이 다량의 문서를 읽고 텍스트를 작성하는 부담을 줄이는 데에 있다.**

작업의 기본 구성은 다음과 같다
```
project_gamma/
├── .gitignore
├── CLAUDE.md
├── PLAN.md                                    # 작업 계획 저장
├── LOG.md                                     # 작업 기록 저장
├── README.md                                  # 시스템의 사용법 등의 기초 정보
├── config.yaml                                # 단일 제어 지점 (모델/임계값/모드/디바이스)
├── requirements.txt                           # 시스템에서 요구되는 PyPI 패키지
├── backend/                                   # 모델과 관련된 작업
├── frontend/                                  # 사용자가 화면상으로 문서를 전달하고 그 결과를 확인
├── model/                                     # 입력될 문서 이미지의 정보를 분석하는 모델
└── data/                                      # 모델 평가에 사용할 데이터와 그 결과들을 저장
```

고려 사항은 다음과 같다. 
- 시스템에서 사용될 모든 변수는 통합적으로 관리되어야 한다. 
- 뼈대가 되는 시스템이 존재해야하며, 서로 다른 모델의 입출력은 그에 맞춰 적절히 변환되어야 한다. 
- 시스템 관리를 위해 최대한 간결하게, 필요한 것만을 작성해야 한다. 

모든 작업은 위와 같은 구성 요소를 기반으로 진행된다. 이후 작업을 진행하며 필요에 의해 추가적으로 생성되거나 수정될 수 있다. 

## 3. frontend에 대하여

**frontend에서는 사용자가 이미지를 쉽게 전달하고 결과를 쉽게 확인하며 그 결과를 쉽게 수정할 수 있어야 한다.**

frontend의 구성 및 설명은 아래와 같다.
```
  Model            Device          Upload Images or PDFs      Analysis and Stop Button
┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐ ┌───────────────────────┐
|              | |              | |                       | | ┌──────────┐ ┌──────┐ |
| Select Model | | CPU □  GPU □ | | Select Images or PDFs | | | Analysis | | Stop | |
|              | |              | |                       | | └──────────┘ └──────┘ |
└──────────────┘ └──────────────┘ └───────────────────────┘ └───────────────────────┘
  Image List           Image                Image Summary                                                 
┌───────────────────┐ ┌────────────────┐  ┌─────────────────────────────────────────────────────────────┐
| Image 1 - Done    │ |                |  │ Full Name: [Predicted Answer] [Accuracy]                    |
| Image 2 - Working │ | Working Image  |  | Account No. (Bank Name): [Predicted Answer] [Accuracy]      |
| Image 3 -         │ | in Now         |  | Resident Registration Number: [Predicted Answer] [Accuracy] |
| Image 4 -         │ |                |  | Address: [Predicted Answer] [Accuracy]                      |
| ...               │ |                |  | Phone Number: [Predicted Answer] [Accuracy]                 |
└───────────────────┘ └────────────────┘  └─────────────────────────────────────────────────────────────┘
 Complete Button
┌──────────┐
| Complete |
└──────────┘
  Preview
┌───────────────────────────────────────┐
| Update Documet like Exel in real-time |
└───────────────────────────────────────┘
 ...
```
초기 화면에 띄워질 것은 아래와 같다.  
- "Model" : 사용 가능한 모델 중 택일
- "Device" : 분석 환경 (CPU or GPU) 설정
- "Image Upload Button" : 둘 이상의 이미지 등록
- "Analysis Button"
    - Model, Device, Image Upload Button의 선택이 완료되면 활성화되며, 지정된 설정으로 작업이 실시 
    - 작업이 진행 중이면 해당 버튼은 Stop Button으로 바뀐다.
- "Stop Button" : 진행중인 작업을 중지한다. 이후 Analysis Button으로 바뀐다. 

작업이 진행될 경우 아래의 구성이 나타난다. 
- "Image List" : 전달받은 이미지 목록과 함께 각 이미지의 상태가 뜬다. 
    - 상태 : 작업 종료(Done), 작업 중(Working), 미작업(Blank)
    - 이미지 목록을 클릭하면 해당 이미지의 작업 화면을 띄울 수 있다. 이미 진행된 작업의 경우 그 작업 기록이 뜬다.
- "Image" : 현재 선택된 이미지
- "Image Summary" : 현재 선택된 이미지의 요약본. Predicted Answer의 수정이 가능. 
- "Complete Button" : 현재 선택된 이미지의 작업이 완료되었을 때 누르는 확인 버튼. 
    - 해당 버튼을 누르면 Image List에서 현재 이미지 상태가 Working에서 Done으로 바뀐 뒤, 다음 이미지로 넘어간다.
- "Preview" : Done으로 처리된 이미지의 정보를 저장했을 때의 결과물을 실시간으로 보여주는 화면이다. 
    - Exel과 같은 sheet 형태로 결과물을 저장한다고 가정한다.

backend와의 연결은 다음과 같다.
- `Image Upload Button` 클릭 시, 선택된 여러 개의 이미지 경로를 backend로 전달한다. 
- `Analysis Button` 클릭 시, 선택된 `Model`, `Device`를 전달해 분석 환경을 전달한다. 
- `Stop Button` 클릭 시, backend에 모든 작업을 중지하라고 신호를 전달한다. 
- 전달받은 이미지에 대한 모델 출력을 적절히 정제한 backend의 신호를 받아 화면에 띄운다. 
- 작업자가 각 이미지에 대하여 작업한 기록을 backend에 전달하여 효율적으로 저장한다. 

## 4. backend에 대하여

**backend는 frontend의 신호를 받아들여 모델을 적절히 활성화하고, 모델 출력을 frontend에 적절히 변환하여 전달한다.**

backend의 기본적인 흐름은 다음과 같다. 
```
get information from frontend → set environment → use model → transform model output to frontend
```

backend의 요구 사항은 아래와 같다. 
- model의 추가나 삭제, 그리고 교체가 자유로워야 한다. 
- model은 Jupyter hub를 통해 제공되는 서버의 GPU를 사용해야 한다. 
- 서로 다른 모델 출력을 통일시킨 뒤 적절히 변환하여 frontend에 전달해야 한다. 

## 5. 개선점에 대하여
필요
- 작업을 중간에 정지할 수 있어야 하며, 그 때까지의 작업 기록이 남아있는 기능
- 이미지와 요약본 이미지를 쉽게 비교할 수 있는 기능 (이미지가 너무 작거나 비교하기 불편한 점 등)

고려
- 작업 결과물을 저장할 파일을 선택하여, 저장된 기록에 이어 새로운 기록을 저장하는 기능
- 작업의 결과물을 새로운 학습 데이터로 저장하고 활용할 수 있는 시스템 (작업을 진행할 수록 모델 발전 가능)
- Exel 등의 sheet 작업물 이외의 형태로 저장하는 기능