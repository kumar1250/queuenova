# Smart Queue Management System - Project Diagrams

Use these [Mermaid](https://mermaid.js.org/) diagrams for your project report. You can paste them into any Markdown viewer (like GitHub or VS Code) or use the Mermaid Live Editor.

## 1. System Architecture
```mermaid
graph TD
    User((User/Client)) -->|Web Interface| UI[Frontend: Bootstrap/HTML/JS]
    UI -->|HTTP Requests| Django[Django Backend Server]
    Django -->|ORM| DB[(MySQL Database)]
    Django -->|Auth| UserDB[User Authentication]
    Django -->|Process| Logic[Token & Queue Logic]
    Logic -->|Generate| QR[QR Code Generator]
    Logic -->|Calculate| Analytics[Queue Analytics]
    Admin((Admin/Staff)) -->|Management| Dashboard[Admin Dashboard]
    Dashboard --> Django
```

## 2. Data Flow Diagram (DFD - Level 1)
```mermaid
graph LR
    User[User] -->|Fill Form| P1(Token Generation)
    P1 -->|Store Data| D1[(Database)]
    P1 -->|Issue| T[Token & QR Code]
    User -->|Payment| P2(Payment Processing)
    P2 -->|Update Status| D1
    Admin[Admin] -->|Update Status| P3(Queue Management)
    P3 -->|Update| D1
    D1 -->|Read| P4(Live Display)
    P4 -->|Show| Display[Public Screen]
```

## 3. Use Case Diagram
```mermaid
useCaseDiagram
    actor "User" as U
    actor "Admin/Staff" as A
    actor "System Admin" as SA

    package "Smart Queue System" {
        usecase "Register/Login" as UC1
        usecase "Join Queue (Get Token)" as UC2
        usecase "Make Payment" as UC3
        usecase "View Token Status" as UC4
        usecase "Cancel Token" as UC5
        usecase "View My Token History" as UC6
        
        usecase "Manage Queue (Call Next)" as UC7
        usecase "Update Token Status" as UC8
        usecase "View Analytics" as UC9
        
        usecase "Setup Organization/Services" as UC10
        usecase "Design Dynamic Forms" as UC11
    }

    U --> UC1
    U --> UC2
    U --> UC3
    U --> UC4
    U --> UC5
    U --> UC6

    A --> UC7
    A --> UC8
    A --> UC9

    SA --> UC10
    SA --> UC11
    SA --> UC1
```

## 4. Entity Relationship Diagram (ERD)
```mermaid
erDiagram
    ORGANIZATION ||--o{ SERVICE : offers
    SERVICE ||--o{ FORMFIELD : defines
    SERVICE ||--o{ TOKEN : has
    USER ||--o{ TOKEN : owns
    TOKEN ||--o{ TOKENFORMDATA : contains
    TOKEN ||--o{ NOTIFICATION : triggers
    PAYMENT ||--|| TOKEN : validates
```
