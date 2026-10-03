"""
Prayash — Personalized Learning Roadmap Generator
==================================================
Generates a personalized, detailed learning roadmap based on:
  - User's extracted skills
  - Target career
  - Skill gap analysis (missing vs existing skills)
  - Skill priorities (high/medium/low)
  - Learning dependencies

The roadmap is organized into 5 phases:
  1. Foundation — Core fundamentals the user needs
  2. Intermediate — Build on fundamentals
  3. Advanced — Master advanced concepts
  4. Practical Projects — Apply knowledge in real projects
  5. Job Ready — Prepare for the job market

Each skill entry contains detailed information including:
  - Description, difficulty, estimated time
  - Why the user needs it
  - Prerequisites
  - Topics to learn
  - Practice exercises
  - Projects
  - Verified learning resources
  - Assessment checklist

Author: Prayash CareerAI
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("prayash.roadmap")

BASE_DIR = Path(__file__).resolve().parent
RESOURCES_PATH = BASE_DIR / "data" / "learning_resources.json"


def _load_resources() -> dict[str, Any]:
    """Load the curated learning resources dataset."""
    if RESOURCES_PATH.exists():
        try:
            with open(RESOURCES_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            log.warning("Failed to load learning resources from %s", RESOURCES_PATH)
    return {}


# ── Skill Knowledge Base ────────────────────────────────────────────
# Maps skills to their detailed information for roadmap generation.

_SKILL_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "python": {
        "name": "Python",
        "description": "A versatile, high-level programming language widely used in web development, data science, automation, and AI/ML.",
        "difficulty": "Beginner",
        "estimated_time": "3-4 weeks",
        "why_needed": "Python is one of the most in-demand programming languages and a core requirement for many tech roles. It provides the foundation for data science, automation, and backend development.",
        "phase": 1,
        "priority_weight": 10,
    },
    "javascript": {
        "name": "JavaScript",
        "description": "The primary language of the web, used for frontend interactivity, backend development (Node.js), and mobile apps.",
        "difficulty": "Beginner",
        "estimated_time": "4-6 weeks",
        "why_needed": "JavaScript is essential for web development. It runs in every browser and is used for building interactive user interfaces and server-side applications.",
        "phase": 1,
        "priority_weight": 10,
    },
    "html": {
        "name": "HTML",
        "description": "The standard markup language for creating web pages and web applications.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "HTML is the building block of all web pages. Understanding HTML is essential for any web-related role.",
        "phase": 1,
        "priority_weight": 8,
    },
    "css": {
        "name": "CSS",
        "description": "The language used to style and layout web pages, controlling colors, fonts, spacing, and responsive design.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "CSS makes web pages visually appealing and responsive. It's essential for frontend development and user experience design.",
        "phase": 1,
        "priority_weight": 8,
    },
    "react": {
        "name": "React",
        "description": "A JavaScript library for building user interfaces, maintained by Meta. Used for creating interactive, component-based UIs.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "React is the most popular frontend framework and is required by most modern frontend and full-stack developer roles.",
        "prerequisites": ["JavaScript", "HTML", "CSS"],
        "phase": 2,
        "priority_weight": 7,
    },
    "vue": {
        "name": "Vue.js",
        "description": "A progressive JavaScript framework for building user interfaces and single-page applications.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Vue.js is a growing frontend framework with excellent documentation, used by many companies for building modern web applications.",
        "prerequisites": ["JavaScript", "HTML", "CSS"],
        "phase": 2,
        "priority_weight": 6,
    },
    "angular": {
        "name": "Angular",
        "description": "A platform and framework for building single-page client applications using HTML and TypeScript.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Angular is widely used in enterprise applications and provides a complete solution for frontend development.",
        "prerequisites": ["JavaScript", "TypeScript"],
        "phase": 2,
        "priority_weight": 6,
    },
    "sql": {
        "name": "SQL",
        "description": "Structured Query Language for managing and querying relational databases.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "SQL is fundamental for data manipulation and analysis. Nearly every application uses a relational database.",
        "phase": 1,
        "priority_weight": 9,
    },
    "git": {
        "name": "Git",
        "description": "A distributed version control system for tracking changes in source code during development.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Git is the industry standard for version control and collaboration. It's essential for any team-based software development.",
        "phase": 1,
        "priority_weight": 8,
    },
    "docker": {
        "name": "Docker",
        "description": "A platform for developing, shipping, and running applications in lightweight, portable containers.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Docker is essential for modern DevOps practices, ensuring consistent environments across development and production.",
        "prerequisites": ["Linux basics"],
        "phase": 3,
        "priority_weight": 6,
    },
    "data structures": {
        "name": "Data Structures",
        "description": "Fundamental data organization methods including arrays, linked lists, trees, graphs, hash tables, and stacks/queues.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Data structures are the backbone of efficient programming. They are critical for coding interviews and writing performant code.",
        "phase": 2,
        "priority_weight": 9,
    },
    "algorithms": {
        "name": "Algorithms",
        "description": "Step-by-step procedures for solving computational problems, including sorting, searching, graph algorithms, and dynamic programming.",
        "difficulty": "Intermediate",
        "estimated_time": "4-6 weeks",
        "why_needed": "Algorithms teach you how to solve problems efficiently and are essential for technical interviews and system optimization.",
        "prerequisites": ["Data Structures"],
        "phase": 2,
        "priority_weight": 9,
    },
    "rest api": {
        "name": "REST APIs",
        "description": "Representational State Transfer APIs for building scalable, stateless web services using HTTP methods.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "REST APIs are the standard for web service communication. Understanding them is essential for building and consuming web services.",
        "prerequisites": ["HTTP basics"],
        "phase": 2,
        "priority_weight": 7,
    },
    "rest apis": {
        "name": "REST APIs",
        "description": "Representational State Transfer APIs for building scalable, stateless web services using HTTP methods.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "REST APIs are the standard for web service communication. Understanding them is essential for building and consuming web services.",
        "prerequisites": ["HTTP basics"],
        "phase": 2,
        "priority_weight": 7,
    },
    "machine learning": {
        "name": "Machine Learning",
        "description": "Algorithms and techniques that enable computers to learn patterns from data and make predictions.",
        "difficulty": "Advanced",
        "estimated_time": "6-8 weeks",
        "why_needed": "Machine learning is transforming every industry. Understanding ML opens doors to high-demand roles in AI and data science.",
        "prerequisites": ["Python", "Statistics"],
        "phase": 3,
        "priority_weight": 7,
    },
    "deep learning": {
        "name": "Deep Learning",
        "description": "Subset of ML using neural networks with multiple layers for complex pattern recognition in data.",
        "difficulty": "Advanced",
        "estimated_time": "6-8 weeks",
        "why_needed": "Deep learning powers modern AI applications like image recognition, NLP, and autonomous systems.",
        "prerequisites": ["Machine Learning", "Python"],
        "phase": 3,
        "priority_weight": 6,
    },
    "statistics": {
        "name": "Statistics",
        "description": "The science of collecting, analyzing, and interpreting data, essential for data-driven decision making.",
        "difficulty": "Beginner",
        "estimated_time": "3-4 weeks",
        "why_needed": "Statistics provides the mathematical foundation for data analysis, machine learning, and making data-driven decisions.",
        "phase": 1,
        "priority_weight": 7,
    },
    "system design": {
        "name": "System Design",
        "description": "The practice of designing large-scale distributed systems, covering architecture, scalability, and trade-offs.",
        "difficulty": "Advanced",
        "estimated_time": "4-6 weeks",
        "why_needed": "System design skills are critical for senior roles and architecture positions. They demonstrate your ability to build scalable applications.",
        "prerequisites": ["Programming basics", "Databases"],
        "phase": 3,
        "priority_weight": 7,
    },
    "ci/cd": {
        "name": "CI/CD",
        "description": "Continuous Integration and Continuous Delivery practices for automating software build, test, and deployment.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "CI/CD is essential for modern software development workflows, enabling rapid and reliable deployments.",
        "prerequisites": ["Git"],
        "phase": 3,
        "priority_weight": 5,
    },
    "node.js": {
        "name": "Node.js",
        "description": "A JavaScript runtime built on Chrome's V8 engine for building scalable server-side applications.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Node.js enables full-stack JavaScript development, making you a versatile developer capable of building complete applications.",
        "prerequisites": ["JavaScript"],
        "phase": 2,
        "priority_weight": 7,
    },
    "java": {
        "name": "Java",
        "description": "A class-based, object-oriented programming language widely used in enterprise applications and Android development.",
        "difficulty": "Beginner",
        "estimated_time": "4-6 weeks",
        "why_needed": "Java is one of the most widely used programming languages in enterprise environments and Android development.",
        "phase": 1,
        "priority_weight": 7,
    },
    "kubernetes": {
        "name": "Kubernetes",
        "description": "An open-source container orchestration platform for automating deployment, scaling, and management of containerized applications.",
        "difficulty": "Advanced",
        "estimated_time": "3-4 weeks",
        "why_needed": "Kubernetes is the industry standard for container orchestration and is essential for DevOps and cloud engineering roles.",
        "prerequisites": ["Docker", "Linux basics"],
        "phase": 3,
        "priority_weight": 5,
    },
    "aws": {
        "name": "AWS",
        "description": "Amazon Web Services — the leading cloud platform offering compute, storage, database, and AI/ML services.",
        "difficulty": "Intermediate",
        "estimated_time": "4-6 weeks",
        "why_needed": "AWS is the most popular cloud platform. Cloud skills are among the most in-demand in the tech industry.",
        "prerequisites": ["Linux basics"],
        "phase": 2,
        "priority_weight": 7,
    },
    "data visualization": {
        "name": "Data Visualization",
        "description": "The graphical representation of data and information using charts, graphs, and maps.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Data visualization skills help communicate insights effectively and are essential for data analysis and reporting roles.",
        "prerequisites": ["Python or JavaScript basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "tableau": {
        "name": "Tableau",
        "description": "A visual analytics platform for transforming data into actionable insights through interactive dashboards.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Tableau is one of the most popular BI tools and is widely used in data analyst and business intelligence roles.",
        "prerequisites": ["SQL basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "statistical analysis": {
        "name": "Statistical Analysis",
        "description": "Applying statistical methods to analyze data, identify patterns, and draw conclusions.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Statistical analysis is fundamental for data-driven decision making in analytics and research roles.",
        "prerequisites": ["Statistics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "reporting": {
        "name": "Reporting & Dashboards",
        "description": "Creating reports and dashboards to communicate data insights to stakeholders.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Reporting skills help you present data insights clearly and drive business decisions.",
        "phase": 2,
        "priority_weight": 4,
    },
    "responsive design": {
        "name": "Responsive Design",
        "description": "Designing web pages that adapt to different screen sizes and devices.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Responsive design is essential for modern web development to ensure a good user experience on all devices.",
        "prerequisites": ["HTML", "CSS"],
        "phase": 1,
        "priority_weight": 6,
    },
    "web performance": {
        "name": "Web Performance",
        "description": "Optimizing web applications for speed, load times, and user experience.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Web performance directly impacts user experience, SEO, and business metrics.",
        "prerequisites": ["HTML", "CSS", "JavaScript"],
        "phase": 3,
        "priority_weight": 5,
    },
    "database design": {
        "name": "Database Design",
        "description": "Designing efficient, normalized database schemas for applications.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Good database design is essential for building scalable, maintainable applications.",
        "prerequisites": ["SQL"],
        "phase": 2,
        "priority_weight": 6,
    },
    "authentication": {
        "name": "Authentication & Authorization",
        "description": "Implementing secure user authentication and authorization systems.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Security is a critical aspect of any web application. Authentication skills are essential for backend development.",
        "prerequisites": ["Programming basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "no sql": {
        "name": "NoSQL Databases",
        "description": "Working with non-relational databases like MongoDB, Redis, and Cassandra.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "NoSQL databases are used for specific use cases like real-time data, caching, and document storage.",
        "prerequisites": ["Programming basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "nosql": {
        "name": "NoSQL Databases",
        "description": "Working with non-relational databases like MongoDB, Redis, and Cassandra.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "NoSQL databases are used for specific use cases like real-time data, caching, and document storage.",
        "prerequisites": ["Programming basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "cloud services": {
        "name": "Cloud Services",
        "description": "Working with cloud platforms like AWS, Azure, or GCP for deploying and managing applications.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Cloud skills are among the most in-demand in the tech industry, enabling scalable application deployment.",
        "phase": 2,
        "priority_weight": 7,
    },
    "azure": {
        "name": "Microsoft Azure",
        "description": "Microsoft's cloud computing platform for building, deploying, and managing applications.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Azure is one of the top cloud platforms and is widely used in enterprise environments.",
        "phase": 2,
        "priority_weight": 6,
    },
    "gcp": {
        "name": "Google Cloud Platform",
        "description": "Google's suite of cloud computing services for building, deploying, and scaling applications.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "GCP offers strong data analytics and ML services, making it valuable for data-focused roles.",
        "phase": 2,
        "priority_weight": 6,
    },
    "version control": {
        "name": "Version Control",
        "description": "Managing and tracking changes to source code using tools like Git.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Version control is essential for collaboration and code management in any development team.",
        "phase": 1,
        "priority_weight": 8,
    },
    "problem solving": {
        "name": "Problem Solving",
        "description": "The ability to analyze problems and develop effective solutions using logical thinking.",
        "difficulty": "Beginner",
        "estimated_time": "Ongoing",
        "why_needed": "Problem solving is the core skill of any technical role and is critical for interviews.",
        "phase": 1,
        "priority_weight": 9,
    },
    "object-oriented programming": {
        "name": "Object-Oriented Programming",
        "description": "A programming paradigm based on objects that combine data and behavior.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "OOP is fundamental to most modern programming languages and software design.",
        "prerequisites": ["Programming basics"],
        "phase": 1,
        "priority_weight": 8,
    },
    "programming": {
        "name": "Programming Fundamentals",
        "description": "Core programming concepts including variables, control flow, functions, and data structures.",
        "difficulty": "Beginner",
        "estimated_time": "3-4 weeks",
        "why_needed": "Programming fundamentals are the foundation of all software development roles.",
        "phase": 1,
        "priority_weight": 10,
    },
    "nlp": {
        "name": "Natural Language Processing",
        "description": "Teaching computers to understand, interpret, and generate human language.",
        "difficulty": "Advanced",
        "estimated_time": "4-6 weeks",
        "why_needed": "NLP is a rapidly growing field essential for AI research and data science roles.",
        "prerequisites": ["Python", "Machine Learning basics"],
        "phase": 3,
        "priority_weight": 6,
    },
    "computer vision": {
        "name": "Computer Vision",
        "description": "Teaching computers to interpret and understand visual information from images and videos.",
        "difficulty": "Advanced",
        "estimated_time": "4-6 weeks",
        "why_needed": "Computer vision is used in autonomous vehicles, medical imaging, and many AI applications.",
        "prerequisites": ["Python", "Deep Learning basics"],
        "phase": 3,
        "priority_weight": 6,
    },
    "pytorch": {
        "name": "PyTorch",
 "description": "An open-source machine learning framework for building and training neural networks.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "PyTorch is the most popular deep learning framework and is widely used in research and industry.",
        "prerequisites": ["Python", "Machine Learning basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "tensorflow": {
        "name": "TensorFlow",
        "description": "An end-to-end open-source machine learning platform by Google.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "TensorFlow is a major ML framework widely used in production environments.",
        "prerequisites": ["Python", "Machine Learning basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "microservices": {
        "name": "Microservices Architecture",
        "description": "Designing applications as a collection of small, independent services.",
        "difficulty": "Advanced",
        "estimated_time": "3-4 weeks",
        "why_needed": "Microservices are the standard architecture for large-scale distributed systems.",
        "prerequisites": ["REST APIs", "Docker"],
        "phase": 3,
        "priority_weight": 6,
    },
    "mlops": {
        "name": "MLOps",
        "description": "Practices for deploying and maintaining ML models in production reliably.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "MLOps bridges the gap between ML research and production, essential for ML engineer roles.",
        "prerequisites": ["Machine Learning", "Docker", "CI/CD"],
        "phase": 3,
        "priority_weight": 6,
    },
    "r": {
        "name": "R Programming",
        "description": "A programming language for statistical computing and data visualization.",
        "difficulty": "Beginner",
        "estimated_time": "3-4 weeks",
        "why_needed": "R is widely used in statistics, data analysis, and academic research.",
        "phase": 1,
        "priority_weight": 5,
    },
    "kotlin": {
        "name": "Kotlin",
        "description": "A modern programming language for Android development and server-side applications.",
        "difficulty": "Beginner",
        "estimated_time": "3-4 weeks",
        "why_needed": "Kotlin is the preferred language for Android development and is fully interoperable with Java.",
        "phase": 1,
        "priority_weight": 6,
    },
    "swift": {
        "name": "Swift",
        "description": "Apple's programming language for iOS, macOS, watchOS, and tvOS development.",
        "difficulty": "Beginner",
        "estimated_time": "3-4 weeks",
        "why_needed": "Swift is essential for iOS/macOS app development in the Apple ecosystem.",
        "phase": 1,
        "priority_weight": 6,
    },
    "mobile ui": {
        "name": "Mobile UI Design",
        "description": "Designing user interfaces specifically for mobile applications.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Mobile UI skills are essential for mobile developer and designer roles.",
        "phase": 2,
        "priority_weight": 5,
    },
    "performance optimization": {
        "name": "Performance Optimization",
        "description": "Techniques to improve application speed, memory usage, and resource efficiency.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Performance optimization is critical for building fast, scalable applications.",
        "phase": 3,
        "priority_weight": 5,
    },
    "api design": {
        "name": "API Design",
        "description": "Designing clean, consistent, and well-documented APIs.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Good API design is essential for building maintainable backend services.",
        "phase": 2,
        "priority_weight": 6,
    },
    "data analysis": {
        "name": "Data Analysis",
        "description": "Inspecting, cleansing, transforming, and modeling data to discover useful information.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Data analysis is the core skill for analyst and data science roles.",
        "prerequisites": ["SQL", "Python or R"],
        "phase": 2,
        "priority_weight": 7,
    },
    "data cleaning": {
        "name": "Data Cleaning",
        "description": "The process of detecting and correcting corrupt or inaccurate records in datasets.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Data cleaning is essential for ensuring data quality and reliable analysis.",
        "prerequisites": ["Python or R", "SQL"],
        "phase": 1,
        "priority_weight": 6,
    },
    "data engineering": {
        "name": "Data Engineering",
        "description": "Designing and building systems for collecting, storing, and analyzing data at scale.",
        "difficulty": "Intermediate",
        "estimated_time": "4-6 weeks",
        "why_needed": "Data engineering is essential for building reliable data infrastructure.",
        "prerequisites": ["Python", "SQL"],
        "phase": 2,
        "priority_weight": 6,
    },
    "data modeling": {
        "name": "Data Modeling",
        "description": "Creating data models that define how data is stored, organized, and accessed.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Data modeling is essential for database design and data warehousing.",
        "prerequisites": ["SQL"],
        "phase": 2,
        "priority_weight": 5,
    },
    "analytics": {
        "name": "Analytics",
        "description": "The systematic computational analysis of data or statistics.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Analytics skills are essential for data-driven decision making.",
        "phase": 2,
        "priority_weight": 6,
    },
    "dashboarding": {
        "name": "Dashboarding",
        "description": "Creating interactive dashboards to visualize and monitor key metrics.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Dashboarding is essential for communicating data insights to stakeholders.",
        "phase": 2,
        "priority_weight": 5,
    },
    "leadership": {
        "name": "Leadership",
        "description": "The ability to guide, motivate, and direct a team toward achieving goals.",
        "difficulty": "Intermediate",
        "estimated_time": "Ongoing",
        "why_needed": "Leadership skills are essential for management and senior roles.",
        "phase": 2,
        "priority_weight": 5,
    },
    "communication": {
        "name": "Communication",
        "description": "The ability to convey information effectively to different audiences.",
        "difficulty": "Beginner",
        "estimated_time": "Ongoing",
        "why_needed": "Communication is essential for collaboration and stakeholder management.",
        "phase": 1,
        "priority_weight": 6,
    },
    "jira": {
        "name": "JIRA",
        "description": "A project management tool for tracking issues, bugs, and agile workflows.",
        "difficulty": "Beginner",
        "estimated_time": "1 week",
        "why_needed": "JIRA is the most widely used project management tool in software development.",
        "phase": 1,
        "priority_weight": 4,
    },
    "ms project": {
        "name": "MS Project",
        "description": "Microsoft's project management software for planning and tracking projects.",
        "difficulty": "Beginner",
        "estimated_time": "1 week",
        "why_needed": "MS Project is commonly used in traditional project management environments.",
        "phase": 1,
        "priority_weight": 3,
    },
    "incident response": {
        "name": "Incident Response",
        "description": "The process of responding to and managing security breaches or cyber attacks.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Incident response is essential for cybersecurity roles.",
        "prerequisites": ["Security basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "firewalls": {
        "name": "Firewalls",
        "description": "Network security devices that monitor and filter incoming/outgoing network traffic.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Firewall management is essential for network security roles.",
        "prerequisites": ["Networking basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "network security": {
        "name": "Network Security",
        "description": "Protecting computer networks from unauthorized access and attacks.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Network security is essential for cybersecurity and infrastructure roles.",
        "prerequisites": ["Networking basics"],
        "phase": 2,
        "priority_weight": 7,
    },
    "vulnerability assessment": {
        "name": "Vulnerability Assessment",
        "description": "Identifying and evaluating security vulnerabilities in systems and networks.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Vulnerability assessment is a core cybersecurity skill.",
        "prerequisites": ["Security basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "siem": {
        "name": "SIEM",
        "description": "Security Information and Event Management for real-time security monitoring.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "SIEM tools are essential for security operations and monitoring.",
        "prerequisites": ["Security basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "security tools": {
        "name": "Security Tools",
        "description": "Various software tools used for protecting systems and networks.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Proficiency with security tools is essential for cybersecurity roles.",
        "phase": 2,
        "priority_weight": 5,
    },
    "automation": {
        "name": "Automation",
        "description": "Using technology to perform tasks with minimal human intervention.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Automation skills improve efficiency and are essential for DevOps and QA roles.",
        "phase": 2,
        "priority_weight": 6,
    },
    "test planning": {
        "name": "Test Planning",
        "description": "Defining the strategy, scope, and approach for testing activities.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Test planning ensures systematic and effective quality assurance.",
        "phase": 2,
        "priority_weight": 5,
    },
    "api testing": {
        "name": "API Testing",
        "description": "Testing APIs for functionality, reliability, performance, and security.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "API testing is essential for ensuring backend service quality.",
        "prerequisites": ["REST APIs"],
        "phase": 2,
        "priority_weight": 5,
    },
    "reinforcement learning": {
        "name": "Reinforcement Learning",
        "description": "A type of machine learning where agents learn optimal actions through trial and error.",
        "difficulty": "Advanced",
        "estimated_time": "4-6 weeks",
        "why_needed": "Reinforcement learning is used in robotics, gaming, and autonomous systems.",
        "prerequisites": ["Machine Learning", "Python"],
        "phase": 3,
        "priority_weight": 5,
    },
    "mathematics": {
        "name": "Mathematics",
        "description": "Core mathematical concepts including linear algebra, calculus, and probability.",
        "difficulty": "Beginner",
        "estimated_time": "4-6 weeks",
        "why_needed": "Mathematics is the foundation for machine learning, data science, and algorithms.",
        "phase": 1,
        "priority_weight": 7,
    },
    "project planning": {
        "name": "Project Planning",
        "description": "Defining project scope, timeline, resources, and deliverables.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Project planning is essential for project managers and team leads.",
        "phase": 1,
        "priority_weight": 5,
    },
    "market analysis": {
        "name": "Market Analysis",
        "description": "Researching market conditions to identify opportunities and threats.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Market analysis is essential for product managers and business roles.",
        "phase": 2,
        "priority_weight": 4,
    },
    "content management": {
        "name": "Content Management",
        "description": "Creating, organizing, and publishing digital content effectively.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Content management skills are essential for technical writing and documentation roles.",
        "phase": 1,
        "priority_weight": 4,
    },
    "markdown": {
        "name": "Markdown",
        "description": "A lightweight markup language for creating formatted text documents.",
        "difficulty": "Beginner",
        "estimated_time": "1 week",
        "why_needed": "Markdown is essential for writing documentation, README files, and notes.",
        "phase": 1,
        "priority_weight": 4,
    },
    "app architecture": {
        "name": "Application Architecture",
        "description": "Designing the structure and organization of software applications.",
        "difficulty": "Advanced",
        "estimated_time": "3-4 weeks",
        "why_needed": "Architecture skills are essential for senior developer and architect roles.",
        "prerequisites": ["Programming fundamentals", "Design patterns"],
        "phase": 3,
        "priority_weight": 6,
    },
    "big data tools": {
        "name": "Big Data Tools",
        "description": "Working with large-scale data processing tools like Hadoop, Spark, and Kafka.",
        "difficulty": "Advanced",
        "estimated_time": "4-6 weeks",
        "why_needed": "Big data skills are essential for data engineering roles working with large datasets.",
        "prerequisites": ["Python", "SQL"],
        "phase": 3,
        "priority_weight": 5,
    },
    "feature engineering": {
        "name": "Feature Engineering",
        "description": "Creating and selecting input variables for machine learning models.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Feature engineering is critical for building effective ML models and is a key skill for ML engineers.",
        "prerequisites": ["Python", "Statistics", "Machine Learning basics"],
        "phase": 3,
        "priority_weight": 6,
    },
    "model deployment": {
        "name": "Model Deployment",
        "description": "Deploying machine learning models to production environments.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Deploying models is essential for ML engineers to make their models available to users.",
        "prerequisites": ["Python", "Machine Learning", "Docker"],
        "phase": 3,
        "priority_weight": 5,
    },
    "a/b testing": {
        "name": "A/B Testing",
        "description": "Designing and analyzing controlled experiments to compare two or more variants.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "A/B testing is essential for data-driven product decisions and optimization.",
        "prerequisites": ["Statistics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "stakeholder management": {
        "name": "Stakeholder Management",
        "description": "Effectively communicating and managing relationships with project stakeholders.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Stakeholder management is essential for product managers and team leads.",
        "phase": 2,
        "priority_weight": 4,
    },
    "roadmapping": {
        "name": "Product Roadmapping",
        "description": "Creating and managing product roadmaps to communicate strategy and priorities.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Roadmapping is a core product management skill for communicating vision and priorities.",
        "phase": 2,
        "priority_weight": 5,
    },
    "wireframing": {
        "name": "Wireframing",
        "description": "Creating low-fidelity layouts to plan user interface structure and flow.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Wireframing is a fundamental UX design skill for planning and communicating design ideas.",
        "phase": 1,
        "priority_weight": 5,
    },
    "prototyping": {
        "name": "Prototyping",
        "description": "Creating interactive prototypes to test and validate design concepts.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Prototyping helps validate design decisions before development and is essential for UX roles.",
        "phase": 2,
        "priority_weight": 5,
    },
    "usability testing": {
        "name": "Usability Testing",
        "description": "Conducting tests to evaluate how easy a product is to use.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Usability testing is essential for ensuring products meet user needs and expectations.",
        "phase": 2,
        "priority_weight": 5,
    },
    "visual design": {
        "name": "Visual Design",
        "description": "Creating visually appealing and consistent designs for digital products.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Visual design skills are essential for creating polished, professional-looking interfaces.",
        "phase": 2,
        "priority_weight": 5,
    },
    "interaction design": {
        "name": "Interaction Design",
        "description": "Designing how users interact with digital products and interfaces.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Interaction design ensures products are intuitive and enjoyable to use.",
        "phase": 2,
        "priority_weight": 5,
    },
    "information architecture": {
        "name": "Information Architecture",
        "description": "Organizing and structuring content to help users find information easily.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Information architecture is fundamental for creating usable, navigable products.",
        "phase": 2,
        "priority_weight": 4,
    },
    "design systems": {
        "name": "Design Systems",
        "description": "Creating and maintaining consistent design patterns and components across products.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Design systems ensure consistency and efficiency in design and development teams.",
        "prerequisites": ["Figma", "Visual Design"],
        "phase": 3,
        "priority_weight": 4,
    },
    "technical communication": {
        "name": "Technical Communication",
        "description": "Creating clear, accurate technical documentation and communications.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "Technical communication is essential for documentation, API docs, and knowledge sharing.",
        "phase": 1,
        "priority_weight": 4,
    },
    "documentation": {
        "name": "Documentation",
        "description": "Writing clear technical documentation for software and APIs.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Good documentation is essential for maintainability and onboarding.",
        "phase": 1,
        "priority_weight": 5,
    },
    "editing": {
        "name": "Editing & Proofreading",
        "description": "Reviewing and improving written content for clarity, accuracy, and style.",
        "difficulty": "Beginner",
        "estimated_time": "1 week",
        "why_needed": "Editing skills are essential for creating professional, polished content.",
        "phase": 1,
        "priority_weight": 3,
    },
    "research": {
        "name": "Research Skills",
        "description": "Conducting thorough research to gather information and insights.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Research skills are fundamental for making informed decisions in any role.",
        "phase": 1,
        "priority_weight": 4,
    },
    "api documentation": {
        "name": "API Documentation",
        "description": "Creating clear, comprehensive documentation for APIs.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "API documentation is essential for developer experience and API adoption.",
        "prerequisites": ["REST APIs"],
        "phase": 2,
        "priority_weight": 5,
    },
    "performance testing": {
        "name": "Performance Testing",
        "description": "Testing application performance, load handling, and optimization.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Performance testing ensures applications can handle real-world usage demands.",
        "prerequisites": ["Testing"],
        "phase": 3,
        "priority_weight": 5,
    },
    "bug tracking": {
        "name": "Bug Tracking",
        "description": "Managing and tracking software bugs and issues effectively.",
        "difficulty": "Beginner",
        "estimated_time": "1 week",
        "why_needed": "Bug tracking is essential for maintaining software quality and team collaboration.",
        "phase": 1,
        "priority_weight": 4,
    },
    "team management": {
        "name": "Team Management",
        "description": "Leading and managing teams effectively.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Team management skills are essential for leadership and management roles.",
        "phase": 2,
        "priority_weight": 5,
    },
    "budgeting": {
        "name": "Budgeting",
        "description": "Managing project budgets and financial planning.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Budgeting skills are essential for project managers and business leaders.",
        "phase": 2,
        "priority_weight": 4,
    },
    "risk management": {
        "name": "Risk Management",
        "description": "Identifying, assessing, and mitigating project and business risks.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Risk management is essential for project success and business continuity.",
        "phase": 2,
        "priority_weight": 5,
    },
    "backup & recovery": {
        "name": "Backup & Recovery",
        "description": "Implementing and managing data backup and disaster recovery procedures.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Backup and recovery skills are essential for database administrators and operations roles.",
        "prerequisites": ["SQL", "Linux basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "performance tuning": {
        "name": "Performance Tuning",
        "description": "Optimizing database and application performance.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Performance tuning is essential for ensuring applications run efficiently at scale.",
        "prerequisites": ["SQL", "Database design"],
        "phase": 3,
        "priority_weight": 5,
    },
    "migration": {
        "name": "Database Migration",
        "description": "Migrating data between databases and systems safely.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Database migration skills are essential for system upgrades and platform changes.",
        "prerequisites": ["SQL"],
        "phase": 2,
        "priority_weight": 4,
    },
    "monitoring": {
        "name": "Monitoring & Observability",
        "description": "Setting up monitoring, logging, and alerting for applications.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Monitoring is essential for maintaining application reliability and performance.",
        "phase": 2,
        "priority_weight": 5,
    },
    "networking": {
        "name": "Networking",
        "description": "Understanding computer networking concepts, protocols, and configuration.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Networking knowledge is essential for DevOps, cloud, and infrastructure roles.",
        "phase": 2,
        "priority_weight": 6,
    },
    "security": {
        "name": "Security Fundamentals",
        "description": "Understanding cybersecurity principles, best practices, and threat mitigation.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Security skills are essential for protecting applications and data from threats.",
        "phase": 2,
        "priority_weight": 7,
    },
    "scripting": {
        "name": "Scripting",
        "description": "Writing scripts to automate tasks and streamline workflows.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "Scripting skills help automate repetitive tasks and improve productivity.",
        "phase": 1,
        "priority_weight": 5,
    },
    "compliance": {
        "name": "Compliance & Regulations",
        "description": "Understanding and implementing regulatory compliance requirements.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Compliance knowledge is essential for roles in regulated industries.",
        "phase": 2,
        "priority_weight": 5,
    },
    "cloud databases": {
        "name": "Cloud Databases",
        "description": "Working with cloud-based database services like RDS, Cloud SQL, and CosmosDB.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Cloud database skills are essential for modern cloud-native application development.",
        "prerequisites": ["SQL", "Cloud basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "typescript": {
        "name": "TypeScript",
        "description": "A strongly-typed superset of JavaScript that adds static type checking and advanced OOP features.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "TypeScript improves code quality and maintainability. It's increasingly required for professional frontend and backend development.",
        "prerequisites": ["JavaScript"],
        "phase": 2,
        "priority_weight": 6,
    },
    "testing": {
        "name": "Testing",
        "description": "Software testing practices including unit testing, integration testing, and end-to-end testing.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Testing ensures software quality and reliability. It's a critical skill for professional software development.",
        "prerequisites": ["Programming basics"],
        "phase": 2,
        "priority_weight": 7,
    },
    "linux": {
        "name": "Linux",
        "description": "An open-source operating system kernel, essential for server administration and DevOps.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "Linux is the most common server operating system. Command-line proficiency is essential for development and DevOps.",
        "phase": 1,
        "priority_weight": 7,
    },
    "terraform": {
        "name": "Terraform",
        "description": "An Infrastructure as Code (IaC) tool by HashiCorp for provisioning and managing cloud infrastructure.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Terraform enables infrastructure automation and is a key skill for DevOps and cloud engineering roles.",
        "prerequisites": ["Cloud basics"],
        "phase": 3,
        "priority_weight": 5,
    },
    "airflow": {
        "skill": "Apache Airflow",
        "name": "Apache Airflow",
        "description": "A platform for programmatically authoring, scheduling, and monitoring data pipelines.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Airflow is the industry standard for data pipeline orchestration and is essential for data engineering roles.",
        "prerequisites": ["Python", "SQL"],
        "phase": 2,
        "priority_weight": 6,
    },
    "figma": {
        "name": "Figma",
        "description": "A collaborative interface design tool for creating UI/UX designs, prototypes, and design systems.",
        "difficulty": "Beginner",
        "estimated_time": "2-3 weeks",
        "why_needed": "Figma is the leading design tool for modern product teams. Design skills are valuable for frontend developers and designers.",
        "phase": 2,
        "priority_weight": 5,
    },
    "power bi": {
        "name": "Power BI",
        "description": "A Microsoft business analytics service for creating interactive data visualizations and business intelligence reports.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Power BI is widely used for business intelligence and data reporting in enterprises.",
        "prerequisites": ["SQL basics", "Excel basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "agile/scrum": {
        "name": "Agile/Scrum",
        "description": "An iterative project management framework for delivering software in small, incremental cycles.",
        "difficulty": "Beginner",
        "estimated_time": "1-2 weeks",
        "why_needed": "Agile/Scrum is the dominant methodology in software development. Understanding it is essential for team-based projects.",
        "phase": 1,
        "priority_weight": 6,
    },
    "kafka": {
        "name": "Apache Kafka",
        "description": "A distributed event streaming platform for building real-time data pipelines and streaming applications.",
        "difficulty": "Advanced",
        "estimated_time": "2-3 weeks",
        "why_needed": "Kafka is the leading platform for real-time data streaming and is critical for data engineering and backend roles.",
        "prerequisites": ["Programming basics", "Distributed systems"],
        "phase": 3,
        "priority_weight": 5,
    },
    "spark": {
        "name": "Apache Spark",
        "description": "A unified analytics engine for large-scale data processing with built-in modules for SQL, streaming, ML, and graph processing.",
        "difficulty": "Advanced",
        "estimated_time": "3-4 weeks",
        "why_needed": "Spark is the most popular big data processing engine and is essential for data engineering and data science roles.",
        "prerequisites": ["Python", "SQL"],
        "phase": 3,
        "priority_weight": 6,
    },
    "etl": {
        "name": "ETL",
        "description": "Extract, Transform, Load — the process of moving data from sources to data warehouses for analysis.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "ETL processes are fundamental to data engineering and analytics pipelines.",
        "prerequisites": ["SQL", "Python"],
        "phase": 2,
        "priority_weight": 6,
    },
    "data warehousing": {
        "name": "Data Warehousing",
        "description": "The process of collecting and managing data from varied sources to provide meaningful business insights.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Data warehousing is essential for business intelligence and analytics roles.",
        "prerequisites": ["SQL"],
        "phase": 2,
        "priority_weight": 5,
    },
    "cybersecurity": {
        "name": "Cybersecurity",
        "description": "The practice of protecting systems, networks, and data from digital attacks and unauthorized access.",
        "difficulty": "Intermediate",
        "estimated_time": "4-6 weeks",
        "why_needed": "Cybersecurity skills are in extremely high demand as organizations face increasing security threats.",
        "prerequisites": ["Networking basics", "Linux basics"],
        "phase": 2,
        "priority_weight": 7,
    },
    "flutter": {
        "name": "Flutter",
        "description": "Google's UI toolkit for building natively compiled mobile, web, and desktop applications from a single codebase.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "Flutter enables cross-platform mobile development with a single codebase, making it a valuable skill for mobile roles.",
        "phase": 2,
        "priority_weight": 6,
    },
    "react native": {
        "name": "React Native",
        "description": "A framework for building native mobile applications using React and JavaScript.",
        "difficulty": "Intermediate",
        "estimated_time": "3-4 weeks",
        "why_needed": "React Native allows web developers to build mobile apps using familiar JavaScript and React patterns.",
        "prerequisites": ["JavaScript", "React basics"],
        "phase": 2,
        "priority_weight": 6,
    },
    "mongodb": {
        "name": "MongoDB",
        "description": "A NoSQL document-oriented database that stores data in flexible, JSON-like documents.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "MongoDB is the leading NoSQL database and is widely used in modern web applications.",
        "phase": 2,
        "priority_weight": 5,
    },
    "redis": {
        "name": "Redis",
        "description": "An open-source, in-memory data structure store used as a database, cache, and message broker.",
        "difficulty": "Intermediate",
        "estimated_time": "1-2 weeks",
        "why_needed": "Redis is essential for caching, session management, and real-time applications.",
        "phase": 3,
        "priority_weight": 4,
    },
    "next.js": {
        "name": "Next.js",
        "description": "A React framework for production with server-side rendering, static site generation, and API routes.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Next.js is the most popular React framework for production applications, offering SSR, SSG, and excellent performance.",
        "prerequisites": ["React", "JavaScript"],
        "phase": 2,
        "priority_weight": 6,
    },
    "selenium": {
        "name": "Selenium",
        "description": "A portable framework for testing web applications across different browsers and platforms.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Selenium is the industry standard for web application testing automation.",
        "prerequisites": ["Programming basics"],
        "phase": 2,
        "priority_weight": 5,
    },
    "product strategy": {
        "name": "Product Strategy",
        "description": "The art and science of defining a product vision, roadmap, and features to achieve business goals.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "Product strategy skills are essential for product managers and aspiring leaders.",
        "phase": 2,
        "priority_weight": 6,
    },
    "user research": {
        "name": "User Research",
        "description": "The practice of understanding user behaviors, needs, and motivations through various research methods.",
        "difficulty": "Intermediate",
        "estimated_time": "2-3 weeks",
        "why_needed": "User research is fundamental to UX design and product development.",
        "phase": 2,
        "priority_weight": 5,
    },
}


def _normalize_skill(skill: str) -> str:
    """Normalize a skill name for lookup."""
    return skill.strip().lower()


def _skill_in_text(skill_name: str, text_lower: str) -> bool:
    """Check if a skill is mentioned in text (fuzzy matching)."""
    s = skill_name.lower()
    # Direct match
    if s in text_lower:
        return True
    # Check common abbreviations/variations
    variations = {
        "javascript": ["js", "javascript"],
        "typescript": ["ts", "typescript"],
        "node.js": ["nodejs", "node.js", "node"],
        "react": ["react", "reactjs"],
        "vue": ["vuejs", "vue.js", "vue"],
        "angular": ["angular", "angularjs"],
        "rest api": ["rest", "restful", "rest api", "rest apis"],
        "sql": ["sql", "mysql", "postgresql", "sqlite"],
        "git": ["git", "github", "gitlab"],
        "machine learning": ["machine learning", "ml"],
        "deep learning": ["deep learning", "dl"],
        "data structures": ["data structures", "ds"],
        "ci/cd": ["ci/cd", "continuous integration", "continuous delivery"],
        "aws": ["aws", "amazon web services"],
        "system design": ["system design", "architecture"],
        "agile/scrum": ["agile", "scrum"],
    }
    for key, vars_list in variations.items():
        if key == s:
            return any(v in text_lower for v in vars_list)
    return False


def _get_skill_phase(skill_key: str, user_has_skill: bool) -> int:
    """Determine the appropriate phase for a skill based on knowledge base."""
    info = _SKILL_KNOWLEDGE.get(skill_key, {})
    return info.get("phase", 2)


def _get_skill_priority(skill_key: str, in_high: bool, in_medium: bool) -> str:
    """Determine skill priority."""
    if in_high:
        return "HIGH"
    if in_medium:
        return "MEDIUM"
    return "LOW"


def _estimate_total_weeks(phases: list[dict[str, Any]]) -> str:
    """Estimate total duration from all phases."""
    total = 0
    for phase in phases:
        for skill in phase.get("skills", []):
            time_str = skill.get("estimated_time", "2 weeks")
            # Parse "3-4 weeks" -> 4 (upper bound)
            parts = time_str.replace("weeks", "").replace("week", "").strip().split("-")
            try:
                total += int(parts[-1].strip())
            except (ValueError, IndexError):
                try:
                    total += int(parts[0].strip())
                except (ValueError, IndexError):
                    total += 2
    return f"{total}-{total + 2} weeks" if total > 0 else "4-6 weeks"


def _generate_weekly_schedule(phases: list[dict[str, Any]], weekly_hours: int = 8) -> list[dict[str, Any]]:
    """Generate a week-by-week learning schedule from the roadmap phases.

    Assigns skills to weeks based on their estimated time and the user's
    available weekly hours. Each week includes the skills to focus on,
    topics to cover, and practice activities.
    """
    weeks: list[dict[str, Any]] = []
    week_num = 0

    for phase in phases:
        for skill in phase.get("skills", []):
            # Skip completed items
            if skill.get("status") == "completed":
                continue
            if skill.get("type") == "project":
                # Projects get 1-2 weeks
                week_num += 1
                weeks.append({
                    "week": week_num,
                    "phase": phase["name"],
                    "skill": skill["name"],
                    "hours": weekly_hours,
                    "topics": skill.get("topics", [])[:6],
                    "practice": skill.get("practice", [])[:3],
                    "project": skill.get("description", ""),
                })
                continue
            if skill.get("type") == "action":
                # Job Ready actions get 1 week each
                week_num += 1
                weeks.append({
                    "week": week_num,
                    "phase": phase["name"],
                    "skill": skill["name"],
                    "hours": weekly_hours,
                    "topics": skill.get("topics", [])[:6],
                    "practice": skill.get("practice", [])[:3],
                    "project": "",
                })
                continue
            # Parse estimated_time to determine number of weeks
            time_str = skill.get("estimated_time", "2-3 weeks")
            num_weeks = 2
            try:
                parts = time_str.replace("weeks", "").replace("week", "").strip().split("-")
                num_weeks = int(parts[-1].strip()) if len(parts) > 1 else int(parts[0].strip())
            except (ValueError, IndexError):
                num_weeks = 2
            num_weeks = max(1, min(num_weeks, 6))  # Clamp between 1 and 6 weeks

            topics = skill.get("topics", [])
            practice = skill.get("practice", [])

            for w in range(num_weeks):
                week_num += 1
                # Split topics across weeks
                topic_start = int(w * len(topics) / num_weeks)
                topic_end = int((w + 1) * len(topics) / num_weeks)
                week_topics = topics[topic_start:topic_end] if topics else []

                week_practice = []
                if w == num_weeks - 1:
                    # Last week gets the practice and project work
                    week_practice = practice[:3]
                else:
                    week_practice = [f"Review {skill['name']} concepts from this week"]

                weeks.append({
                    "week": week_num,
                    "phase": phase["name"],
                    "skill": skill["name"],
                    "hours": weekly_hours,
                    "topics": week_topics,
                    "practice": week_practice,
                    "project": "" if w < num_weeks - 1 else (skill.get("projects", [""])[0] if skill.get("projects") else ""),
                })

    return weeks


def generate_personalized_roadmap(
    resume_text: str,
    target_role: str,
    user_skills: list[str] | None = None,
    missing_skills: list[str] | None = None,
    matched_skills: list[str] | None = None,
    high_priority: list[str] | None = None,
    medium_priority: list[str] | None = None,
    low_priority: list[str] | None = None,
    weekly_hours: int = 8,
) -> dict[str, Any]:
    """Generate a personalized learning roadmap based on skill gaps.

    This function takes the user's current skills, target career, and
    skill gap analysis results to produce a detailed, personalized roadmap
    organized into 5 phases.

    Args:
        resume_text: The user's resume text.
        target_role: The target career role.
        user_skills: List of skills the user already has.
        missing_skills: List of skills the user is missing.
        matched_skills: List of skills that match the target role.
        high_priority: High priority missing skills.
        medium_priority: Medium priority missing skills.
        low_priority: Low priority missing skills.
        weekly_hours: Hours per week the user can commit.

    Returns:
        A structured roadmap dictionary with phases, skills, resources, etc.
    """
    if not resume_text or len(resume_text.strip()) < 10:
        return {"error": "Resume text is required"}

    if not target_role:
        return {"error": "Target role is required"}

    # Load curated resources
    resources_db = _load_resources()

    # Normalize input lists
    user_skills_lower = [_normalize_skill(s) for s in (user_skills or [])]
    missing_skills_list = missing_skills or []
    matched_skills_list = matched_skills or []
    high_prio = [_normalize_skill(s) for s in (high_priority or [])]
    med_prio = [_normalize_skill(s) for s in (medium_priority or [])]

    # Build the roadmap from missing skills
    # Each missing skill gets detailed information
    skill_entries: list[dict[str, Any]] = []

    for skill in missing_skills_list:
        skill_key = _normalize_skill(skill)
        info = _SKILL_KNOWLEDGE.get(skill_key, {})

        # Get resources for this skill
        resources = resources_db.get(skill_key, {}).get("resources", [])

        # Determine priority
        if skill_key in high_prio:
            priority = "HIGH"
        elif skill_key in med_prio:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Determine phase
        phase = info.get("phase", 2)

        # Build the skill entry
        entry: dict[str, Any] = {
            "name": info.get("name", skill.title()),
            "description": info.get("description", f"Learn {skill} to improve your profile for {target_role}."),
            "why_needed": info.get(
                "why_needed",
                f"{skill} is a required skill for {target_role} and is currently missing from your profile.",
            ),
            "difficulty": info.get("difficulty", "Intermediate"),
            "estimated_time": info.get("estimated_time", "2-3 weeks"),
            "priority": priority,
            "phase": phase,
            "prerequisites": info.get("prerequisites", []),
            "current_proficiency": "Not Started",
            "required_proficiency": "Proficient",
            "topics": _get_topics_for_skill(skill_key),
            "practice": _get_practice_for_skill(skill_key),
            "projects": _get_projects_for_skill(skill_key, target_role),
            "assessment": _get_assessment_for_skill(skill_key),
            "resources": _format_resources(resources),
            "status": "not_started",
            "progress": 0,
        }

        # Calculate estimated hours based on difficulty
        diff = entry["difficulty"]
        if diff == "Beginner":
            entry["estimated_hours"] = weekly_hours * 2
        elif diff == "Intermediate":
            entry["estimated_hours"] = weekly_hours * 3
        else:
            entry["estimated_hours"] = weekly_hours * 4

        skill_entries.append(entry)

    # Also add matched skills as "already strong" context
    already_have = []
    for skill in matched_skills_list:
        skill_key = _normalize_skill(skill)
        info = _SKILL_KNOWLEDGE.get(skill_key, {})
        already_have.append({
            "name": info.get("name", skill.title()),
            "status": "matched",
        })

    # Organize skills into 5 phases
    phases = _organize_into_phases(skill_entries)

    # Calculate statistics
    total_skills = len(skill_entries)
    total_weeks_str = _estimate_total_weeks(phases)

    # Calculate potential skill coverage after completing roadmap
    current_match = len(matched_skills_list)
    total_required = len(matched_skills_list) + len(missing_skills_list)
    potential_coverage = round(
        ((current_match + total_skills) / total_required * 100) if total_required > 0 else 0, 1
    )

    roadmap_result = {
        "target_role": target_role,
        "career_match": round(
            (current_match / total_required * 100) if total_required > 0 else 0, 1
        ),
        "current_skill_match": round(
            (current_match / total_required * 100) if total_required > 0 else 0, 1
        ),
        "potential_skill_coverage": potential_coverage,
        "total_skills_to_learn": total_skills,
        "total_matched_skills": len(matched_skills_list),
        "estimated_duration": total_weeks_str,
        "weekly_hours": weekly_hours,
        "already_have": already_have,
        "phases": phases,
        "weekly_schedule": _generate_weekly_schedule(phases, weekly_hours),
        "reskilling_context": _build_reskilling_context(target_role, user_skills_lower),
    }

    return roadmap_result


def _organize_into_phases(skill_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Organize skills into 5 structured phases with proper dependencies."""
    phase_names = ["Foundation", "Intermediate", "Advanced", "Practical Projects", "Job Ready"]
    phase_icons = ["📚", "🔧", "🚀", "💼", "🎯"]
    phase_descriptions = [
        "Build your foundation with core concepts and fundamentals",
        "Expand your skills with intermediate topics and hands-on practice",
        "Master advanced techniques, tools, and architectural patterns",
        "Apply your knowledge through real-world projects",
        "Polish your portfolio, prepare for interviews, and start applying",
    ]

    # Sort skills by their assigned phase, then by priority weight
    sorted_skills = sorted(
        skill_entries,
        key=lambda s: (
            s.get("phase", 2),
            -_SKILL_KNOWLEDGE.get(_normalize_skill(s["name"]), {}).get("priority_weight", 5),
        ),
    )

    phases: list[dict[str, Any]] = []
    for i in range(5):
        phase_skills = [s for s in sorted_skills if s.get("phase", 2) == i + 1]
        if i == 3:  # Practical Projects phase
            # Add project-focused items from all phases
            project_items = []
            for s in sorted_skills:
                for proj in s.get("projects", []):
                    if isinstance(proj, str):
                        project_items.append({
                            "name": f"Project: {proj[:60]}",
                            "description": proj,
                            "difficulty": "Intermediate",
                            "estimated_time": "1-2 weeks",
                            "priority": s.get("priority", "MEDIUM"),
                            "phase": 4,
                            "type": "project",
                            "related_skill": s["name"],
                            "status": "not_started",
                            "progress": 0,
                            "topics": [],
                            "practice": [],
                            "projects": [],
                            "assessment": [],
                            "resources": [],
                        })
                        if len(project_items) >= 4:
                            break
                if len(project_items) >= 4:
                    break
            phase_skills = project_items
        elif i == 4:  # Job Ready phase
            phase_skills = [
                {
                    "name": "Polish Your Portfolio",
                    "description": "Update your GitHub, LinkedIn, and portfolio website with your best projects.",
                    "difficulty": "Beginner",
                    "estimated_time": "1 week",
                    "priority": "HIGH",
                    "phase": 5,
                    "type": "action",
                    "status": "not_started",
                    "progress": 0,
                    "topics": [
                        "Update GitHub profile and pinned repos",
                        "Refresh LinkedIn headline and summary",
                        "Create/update portfolio website",
                        "Write project case studies",
                        "Prepare project demos",
                    ],
                    "practice": [
                        "Review all completed projects",
                        "Write clear README files for each project",
                        "Record demo videos",
                    ],
                    "projects": [],
                    "assessment": [
                        "Portfolio has 3+ quality projects",
                        "LinkedIn profile is complete",
                        "GitHub is active with contributions",
                    ],
                    "resources": [],
                },
                {
                    "name": "Interview Preparation",
                    "description": "Prepare for technical and behavioral interviews with practice questions and mock interviews.",
                    "difficulty": "Intermediate",
                    "estimated_time": "2 weeks",
                    "priority": "HIGH",
                    "phase": 5,
                    "type": "action",
                    "status": "not_started",
                    "progress": 0,
                    "topics": [
                        "Technical interview fundamentals",
                        "Coding challenge practice",
                        "System design interviews",
                        "Behavioral interview questions (STAR method)",
                        "Salary negotiation basics",
                        "Portfolio presentation",
                    ],
                    "practice": [
                        "Solve 5 coding challenges daily",
                        "Practice explaining your projects",
                        "Do mock interviews with peers",
                        "Write and refine your elevator pitch",
                    ],
                    "projects": [],
                    "assessment": [
                        "Can solve medium LeetCode problems consistently",
                        "Can explain all portfolio projects clearly",
                        "Can answer behavioral questions with STAR",
                    ],
                    "resources": [],
                },
                {
                    "name": "Start Applying",
                    "description": "Begin your job search with targeted applications and networking.",
                    "difficulty": "Beginner",
                    "estimated_time": "Ongoing",
                    "priority": "HIGH",
                    "phase": 5,
                    "type": "action",
                    "status": "not_started",
                    "progress": 0,
                    "topics": [
                        "Job search strategies",
                        "Resume tailoring for each application",
                        "Cover letter writing",
                        "Networking on LinkedIn",
                        "Following up on applications",
                    ],
                    "practice": [
                        "Apply to 5-10 jobs per week",
                        "Customize resume for each application",
                        "Reach out to 3 professionals weekly",
                        "Attend tech meetups or virtual events",
                    ],
                    "projects": [],
                    "assessment": [
                        "Tailored resume for target role",
                        "Active LinkedIn presence",
                        "Regular application submissions",
                    ],
                    "resources": [],
                },
            ]

        phases.append({
            "name": phase_names[i],
            "icon": phase_icons[i],
            "description": phase_descriptions[i],
            "skills": phase_skills,
            "completed_count": 0,
            "total_count": len(phase_skills),
            "completion_percentage": 0,
        })

    return phases


def _get_topics_for_skill(skill_key: str) -> list[str]:
    """Get detailed learning topics for a skill."""
    topics_map: dict[str, list[str]] = {
        "python": [
            "Variables and data types",
            "Control flow (if/else, loops)",
            "Functions and scope",
            "Data structures (lists, dicts, sets, tuples)",
            "File I/O",
            "Error handling",
            "Object-oriented programming",
            "Modules and packages",
            "Decorators and generators",
            "Virtual environments",
        ],
        "javascript": [
            "Variables (let, const, var)",
            "Functions and scope",
            "Arrays and objects",
            "DOM manipulation",
            "Events and event handling",
            "ES6+ features",
            "Promises and async/await",
            "Fetch API",
            "Modules (import/export)",
            "Error handling",
        ],
        "react": [
            "React fundamentals and JSX",
            "Components (functional)",
            "Props and state",
            "Hooks (useState, useEffect, useContext)",
            "Event handling",
            "Conditional rendering",
            "Lists and keys",
            "Forms and controlled components",
            "API integration",
            "React Router",
            "Context API",
            "Performance optimization",
        ],
        "sql": [
            "SELECT queries",
            "WHERE clauses and filtering",
            "JOINs (INNER, LEFT, RIGHT)",
            "GROUP BY and HAVING",
            "Aggregation functions",
            "Subqueries",
            "Window functions",
            "Indexing and optimization",
            "Database design",
            "Transactions",
        ],
        "git": [
            "git init, add, commit",
            "git push, pull, fetch",
            "Branching and merging",
            "Git stash",
            "Pull requests",
            "Resolving merge conflicts",
            "Git rebase",
            "GitHub workflows",
            ".gitignore",
        ],
        "docker": [
            "Containers vs virtual machines",
            "Docker images and layers",
            "Dockerfile creation",
            "Docker Compose",
            "Networking between containers",
            "Volumes and data persistence",
            "Docker Hub",
            "Multi-stage builds",
            "Container security",
        ],
        "data structures": [
            "Arrays and strings",
            "Linked lists",
            "Stacks and queues",
            "Hash tables / hash maps",
            "Trees (binary trees, BST, heaps)",
            "Graphs (BFS, DFS)",
            "Tries",
            "Priority queues",
            "Time and space complexity (Big O)",
        ],
        "algorithms": [
            "Sorting algorithms",
            "Binary search",
            "BFS and DFS",
            "Dynamic programming",
            "Greedy algorithms",
            "Divide and conquer",
            "Backtracking",
            "Graph algorithms",
            "Recursion",
            "Sliding window and two pointers",
        ],
        "rest api": [
            "HTTP methods (GET, POST, PUT, DELETE)",
            "Status codes",
            "Request/response cycle",
            "JSON data format",
            "Authentication (API keys, JWT)",
            "Rate limiting",
            "Pagination",
            "Error handling",
            "RESTful design principles",
            "API documentation",
        ],
        "machine learning": [
            "Supervised learning (regression, classification)",
            "Unsupervised learning (clustering)",
            "Model evaluation and validation",
            "Feature engineering",
            "Cross-validation",
            "Decision trees and random forests",
            "Neural networks basics",
            "Gradient descent",
            "Bias-variance tradeoff",
        ],
        "deep learning": [
            "Neural network architecture",
            "Activation functions",
            "Backpropagation",
            "CNNs",
            "RNNs",
            "Transformers and attention",
            "Transfer learning",
            "Regularization techniques",
            "GPU computing basics",
        ],
        "statistics": [
            "Descriptive statistics",
            "Probability distributions",
            "Hypothesis testing",
            "Confidence intervals",
            "Correlation and causation",
            "Regression analysis",
            "Bayesian statistics basics",
            "A/B testing",
            "Statistical significance",
        ],
        "system design": [
            "Scalability concepts",
            "Load balancing",
            "Caching strategies",
            "Database sharding",
            "Message queues",
            "Microservices architecture",
            "API gateway patterns",
            "CAP theorem",
            "Rate limiting",
        ],
        "html": [
            "HTML5 semantic elements",
            "Forms and input types",
            "Tables",
            "Multimedia elements",
            "Links and navigation",
            "Accessibility (ARIA)",
            "SEO basics",
        ],
        "css": [
            "Selectors and specificity",
            "Box model",
            "Flexbox",
            "CSS Grid",
            "Responsive design",
            "CSS variables",
            "Transitions and animations",
            "Typography",
            "Positioning",
        ],
        "node.js": [
            "Node.js fundamentals",
            "NPM",
            "Express.js framework",
            "REST API development",
            "Middleware",
            "File system operations",
            "Event-driven architecture",
            "Async programming",
            "Database integration",
            "Error handling",
        ],
        "aws": [
            "EC2 instances",
            "S3 storage",
            "RDS databases",
            "Lambda serverless",
            "VPC and networking",
            "IAM",
            "CloudWatch monitoring",
            "Cost optimization",
        ],
        "typescript": [
            "Basic types and annotations",
            "Interfaces and type aliases",
            "Functions with types",
            "Generics",
            "Enums",
            "Union and intersection types",
            "Type guards",
            "TypeScript configuration",
        ],
        "testing": [
            "Unit testing",
            "Integration testing",
            "End-to-end testing",
            "Test-driven development (TDD)",
            "Mocking and stubbing",
            "Code coverage",
            "CI testing integration",
        ],
        "linux": [
            "Command line basics",
            "File system navigation",
            "File permissions",
            "Process management",
            "Shell scripting",
            "Package management",
            "Networking commands",
            "User management",
        ],
        "ci/cd": [
            "Continuous Integration concepts",
            "GitHub Actions",
            "Jenkins basics",
            "Automated testing in pipelines",
            "Deployment strategies",
            "Environment variables and secrets",
            "Pipeline as code",
        ],
        "kubernetes": [
            "Kubernetes architecture",
            "Deployments and ReplicaSets",
            "Services and networking",
            "ConfigMaps and Secrets",
            "Persistent volumes",
            "Helm charts",
            "Kubectl commands",
            "Monitoring and logging",
        ],
        "terraform": [
            "HCL syntax",
            "Providers and resources",
            "Variables and outputs",
            "State management",
            "Modules",
            "Workspaces",
            "Import and destroy",
        ],
        "airflow": [
            "DAGs (Directed Acyclic Graphs)",
            "Operators",
            "Tasks and task flows",
            "Scheduling",
            "Hooks and connections",
            "XComs",
            "Monitoring and logging",
        ],
        "figma": [
            "Interface overview",
            "Frames and artboards",
            "Components and variants",
            "Auto layout",
            "Design systems",
            "Prototyping",
            "Plugins",
        ],
        "power bi": [
            "Power BI Desktop interface",
            "Data import and transformation",
            "Data modeling",
            "DAX formulas",
            "Visualizations and charts",
            "Interactive dashboards",
            "Publishing and sharing",
        ],
        "agile/scrum": [
            "Agile Manifesto and principles",
            "Scrum framework",
            "Sprint planning and retrospectives",
            "User stories and story points",
            "Product backlog management",
            "Daily standups",
            "JIRA/Trello tools",
        ],
        "mongodb": [
            "Document model vs relational",
            "CRUD operations",
            "Mongoose ODM",
            "Indexing and performance",
            "Aggregation pipeline",
            "Schema design",
        ],
        "kafka": [
            "Kafka architecture",
            "Producers and consumers",
            "Consumer groups",
            "Kafka Streams",
            "Schema registry",
            "Monitoring and administration",
        ],
        "spark": [
            "Spark architecture",
            "RDDs, DataFrames, Datasets",
            "Spark SQL",
            "PySpark basics",
            "Performance tuning",
            "Integration with Hadoop/S3",
        ],
        "etl": [
            "ETL concepts and pipeline design",
            "Data extraction methods",
            "Data transformation techniques",
            "Data validation",
            "Loading strategies",
            "Error handling in ETL",
        ],
        "data warehousing": [
            "Data warehouse concepts",
            "Star schema and snowflake schema",
            "Dimensional modeling",
            "OLAP vs OLTP",
            "Cloud warehouses",
            "Query optimization",
        ],
        "cybersecurity": [
            "OWASP Top 10",
            "Network security fundamentals",
            "Cryptography basics",
            "Vulnerability assessment",
            "Penetration testing",
            "Incident response",
            "Secure coding practices",
        ],
        "flutter": [
            "Dart language basics",
            "Widgets and widget trees",
            "State management",
            "Navigation and routing",
            "Forms and validation",
            "Networking and APIs",
            "Testing and deployment",
        ],
        "react native": [
            "React Native components",
            "Core components",
            "Navigation",
            "State management",
            "Networking and APIs",
            "Platform-specific code",
            "Testing",
        ],
        "vue": [
            "Vue fundamentals and template syntax",
            "Components and props",
            "Reactive data and watchers",
            "Lifecycle hooks",
            "Vue Router",
            "Pinia state management",
            "Composition API",
        ],
        "angular": [
            "Angular architecture",
            "Components and templates",
            "Services and dependency injection",
            "Routing",
            "Reactive forms",
            "RxJS observables",
            "Angular CLI",
        ],
        "next.js": [
            "Pages and routing",
            "Server-side rendering (SSR)",
            "Static site generation (SSG)",
            "API routes",
            "Data fetching",
            "Image optimization",
            "Deployment (Vercel)",
        ],
        "selenium": [
            "WebDriver setup",
            "Element locators",
            "Actions and interactions",
            "Waits (implicit, explicit)",
            "Page Object Model",
            "Cross-browser testing",
        ],
        "redis": [
            "Data types (strings, lists, sets)",
            "Caching patterns",
            "Pub/Sub messaging",
            "Persistence",
            "Redis with Python/Node.js",
            "Rate limiting",
        ],
        "data visualization": [
            "Chart types",
            "Matplotlib and Seaborn",
            "Plotly and Dash",
            "D3.js basics",
            "Tableau basics",
            "Interactive visualizations",
            "Storytelling with data",
        ],
        "product strategy": [
            "Product vision and mission",
            "Market analysis",
            "Competitive analysis",
            "User personas",
            "Product roadmap",
            "OKRs and KPIs",
            "Go-to-market strategy",
        ],
        "user research": [
            "Qualitative vs quantitative research",
            "User interviews",
            "Usability testing",
            "A/B testing",
            "Personas and journey mapping",
            "Research synthesis",
        ],
        "tableau": [
            "Tableau interface and data connections",
            "Worksheets and dashboards",
            "Chart types and formatting",
            "Calculated fields",
            "Parameters and filters",
            "LOD expressions",
            "Data blending",
            "Publishing and sharing",
        ],
        "statistical analysis": [
            "Descriptive statistics",
            "Hypothesis testing",
            "Confidence intervals",
            "Regression analysis",
            "Correlation analysis",
            "ANOVA",
            "Non-parametric tests",
            "Statistical software (R, Python)",
        ],
        "reporting": [
            "Report design principles",
            "Data aggregation and summarization",
            "Chart selection and formatting",
            "Automated reporting",
            "Dashboard design",
            "Stakeholder communication",
        ],
        "responsive design": [
            "Mobile-first design approach",
            "CSS media queries",
            "Flexbox and Grid for responsive layouts",
            "Responsive images",
            "Breakpoints and viewport units",
            "Testing on multiple devices",
        ],
        "web performance": [
            "Core Web Vitals",
            "Lazy loading",
            "Code splitting",
            "Image optimization",
            "Caching strategies",
            "Performance monitoring tools",
        ],
        "database design": [
            "ER diagrams",
            "Normalization (1NF, 2NF, 3NF)",
            "Schema design",
            "Indexing strategies",
            "Data types and constraints",
            "Relationships (1:1, 1:N, M:N)",
        ],
        "authentication": [
            "Authentication methods (JWT, OAuth, SAML)",
            "Password hashing (bcrypt, argon2)",
            "Session management",
            "Role-based access control (RBAC)",
            "Multi-factor authentication",
            "Security best practices",
        ],
        "no sql": [
            "Document databases (MongoDB)",
            "Key-value stores (Redis)",
            "Column-family (Cassandra)", "Graph databases (Neo4j)",
            "CAP theorem",
            "When to use NoSQL vs SQL",
        ],
        "cloud services": [
            "Cloud computing concepts",
            "IaaS, PaaS, SaaS models",
            "Major cloud providers (AWS, Azure, GCP)",
            "Compute services (EC2, Lambda)",
            "Storage services (S3, Blob Storage)",
            "Cost management",
        ],
        "big data tools": [
            "Hadoop ecosystem",
            "Apache Spark",
            "Apache Kafka",
            "Data lake vs data warehouse",
            "Stream processing vs batch processing",
            "ETL pipelines",
        ],
        "feature engineering": [
            "Feature selection methods",
            "Feature transformation",
            "Encoding categorical variables",
            "Scaling and normalization",
            "Dimensionality reduction",
            "Feature importance analysis",
        ],
        "model deployment": [
            "Model serialization (pickle, ONNX)",
            "REST API for model serving",
            "Containerization of ML models",
            "Model monitoring and drift detection",
            "A/B testing for models",
            "CI/CD for ML pipelines",
        ],
        "a/b testing": [
            "Experimental design",
            "Sample size calculation",
            "Statistical significance",
            "Common pitfalls",
            "Multivariate testing",
            "Bayesian testing",
        ],
        "stakeholder management": [
            "Stakeholder identification",
            "Communication strategies",
            "Managing expectations",
            "Reporting progress",
            "Conflict resolution",
            "Decision-making frameworks",
        ],
        "roadmapping": [
            "Product roadmap types",
            "Prioritization frameworks",
            "Timeline planning",
            "Stakeholder alignment",
            "OKRs and KPIs",
            "Roadmap tools",
        ],
        "wireframing": [
            "Low-fidelity wireframes",
            "Paper prototyping",
            "Digital wireframing tools",
            "Information hierarchy",
            "Layout principles",
            "User flow mapping",
        ],
        "prototyping": [
            "Interactive prototyping tools",
            "Figma prototyping",
            "User testing with prototypes",
            "Iteration and refinement",
            "High-fidelity vs low-fidelity",
            "Animation and transitions",
        ],
        "usability testing": [
            "Test planning and recruitment",
            "Moderated vs unmoderated testing",
            "Task-based testing",
            "Observation and note-taking",
            "Analysis and reporting",
            "Iterating based on feedback",
        ],
        "visual design": [
            "Color theory",
            "Typography",
            "Layout and composition",
            "Visual hierarchy",
            "Brand consistency",
            "Accessibility in design",
        ],
        "interaction design": [
            "Interaction patterns",
            "Microinteractions",
            "User feedback mechanisms",
            "Error states and edge cases",
            "Animation for interaction",
            "Accessibility considerations",
        ],
        "information architecture": [
            "Content audit",
            "Card sorting",
            "Tree testing",
            "Navigation design",
            "Taxonomy and categorization",
            "Search design",
        ],
        "design systems": [
            "Component libraries",
            "Design tokens",
            "Style guides",
            "Documentation standards",
            "Version control for design",
            "Cross-team collaboration",
        ],
        "technical communication": [
            "Technical writing principles",
            "Audience analysis",
            "Document structure",
            "Visual communication",
            "Style guides",
            "Localization considerations",
        ],
        "documentation": [
            "Documentation types (API, user, developer)",
            "Markdown and documentation tools",
            "Documentation best practices",
            "Versioning documentation",
            "Documentation testing",
            "Contributing guidelines",
        ],
        "editing": [
            "Grammar and style",
            "Clarity and conciseness",
            "Technical accuracy",
            "Peer review processes",
            "Style guide adherence",
            "Proofreading techniques",
        ],
        "research": [
            "Research methodology",
            "Source evaluation",
            "Data collection methods",
            "Analysis techniques",
            "Report writing",
            "Citation practices",
        ],
        "api documentation": [
            "OpenAPI/Swagger specification",
            "API reference documentation",
            "Getting started guides",
            "Code examples",
            "Versioning documentation",
            "Interactive API explorers",
        ],
        "performance testing": [
            "Load testing",
            "Stress testing",
            "Spike testing",
            "Performance metrics",
            "Tool selection (JMeter, Locust)",
            "Bottleneck identification",
        ],
        "bug tracking": [
            "Bug reporting best practices",
            "Bug severity and priority",
            "Bug lifecycle management",
            "Tool usage (Jira, GitHub Issues)",
            "Root cause analysis",
            "Regression testing",
        ],
        "team management": [
            "Team building and motivation",
            "Delegation and empowerment",
            "Performance management",
            "Conflict resolution",
            "Hiring and onboarding",
            "Remote team management",
        ],
        "budgeting": [
            "Budget planning",
            "Cost estimation",
            "Financial tracking",
            "Resource allocation",
            "ROI analysis",
            "Variance reporting",
        ],
        "risk management": [
            "Risk identification",
            "Risk assessment and scoring",
            "Mitigation strategies",
            "Risk monitoring",
            "Contingency planning",
            "Risk communication",
        ],
        "backup & recovery": [
            "Backup strategies (full, incremental, differential)",
            "Disaster recovery planning",
            "RPO and RTO concepts",
            "Backup tools and automation",
            "Recovery testing",
            "Data retention policies",
        ],
        "performance tuning": [
            "Query optimization",
            "Index optimization",
            "Memory management",
            "Connection pooling",
            "Caching strategies",
            "Monitoring and profiling",
        ],
        "migration": [
            "Migration planning",
            "Data transformation",
            "Schema migration tools",
            "Testing and validation",
            "Rollback strategies",
            "Downtime minimization",
        ],
        "monitoring": [
            "Monitoring tools (Prometheus, Grafana)",
            "Log management (ELK stack)",
            "Alerting and incident response",
            "SLA and SLO monitoring",
            "APM tools",
            "Capacity planning",
        ],
        "networking": [
            "OSI model",
            "TCP/IP fundamentals",
            "DNS and DHCP",
            "Firewalls and routing",
            "Network security basics",
            "VPN and remote access",
        ],
        "security": [
            "OWASP Top 10",
            "Cryptography basics",
            "Network security",
            "Access control",
            "Security auditing",
            "Incident response",
        ],
        "scripting": [
            "Bash scripting",
            "Python scripting",
            "PowerShell basics",
            "Automation patterns",
            "Error handling in scripts",
            "Scheduling and cron jobs",
        ],
        "compliance": [
            "GDPR fundamentals",
            "HIPAA basics",
            "SOC 2 compliance",
            "Data privacy principles",
            "Audit procedures",
            "Compliance tools",
        ],
        "cloud databases": [
            "Cloud database services",
            "Managed vs self-hosted",
            "Scaling strategies",
            "Backup and recovery in cloud",
            "Cost optimization",
            "Multi-region deployment",
        ],
    }
    return topics_map.get(skill_key, [f"Research and learn {skill_key} fundamentals", f"Practice {skill_key} with hands-on exercises", f"Build a project using {skill_key}"])


def _get_practice_for_skill(skill_key: str) -> list[str]:
    """Get practice exercises for a skill."""
    practice_map: dict[str, list[str]] = {
        "python": [
            "Build a CLI calculator",
            "Create a file organizer script",
            "Solve 30 problems on HackerRank",
            "Build a web scraper with BeautifulSoup",
        ],
        "javascript": [
            "Build a counter app",
            "Build a todo application",
            "Build a weather app using fetch API",
            "Solve 50 challenges on freeCodeCamp",
        ],
        "react": [
            "Build a counter application",
            "Build a todo application",
            "Build a weather dashboard with API",
            "Build a shopping cart",
        ],
        "sql": [
            "Write 50 SQL queries on LeetCode",
            "Practice on Mode Analytics",
            "Design a database schema",
        ],
        "git": [
            "Complete Learn Git Branching tutorial",
            "Practice branching strategies",
            "Contribute to an open-source project via PR",
        ],
        "docker": [
            "Containerize a web application",
            "Set up a multi-container app with Compose",
            "Write optimized Dockerfiles",
        ],
        "data structures": [
            "Solve 50 easy LeetCode problems",
            "Implement each data structure from scratch",
            "Practice on GeeksforGeeks",
        ],
        "algorithms": [
            "Solve 100+ LeetCode problems",
            "Implement sorting algorithms from scratch",
            "Solve 20 dynamic programming problems",
        ],
        "rest api": [
            "Build a CRUD API for a blog",
            "Consume a public API (GitHub, Weather)",
            "Implement JWT authentication",
        ],
        "machine learning": [
            "Complete Andrew Ng's ML course",
            "Solve Kaggle competitions",
            "Build an end-to-end ML project",
        ],
        "statistics": [
            "Complete Khan Academy Statistics course",
            "Analyze real datasets with Python",
            "Perform hypothesis tests",
        ],
        "system design": [
            "Design systems on paper (URL shortener, chat app)",
            "Study system design interview questions",
            "Read engineering blogs from tech companies",
        ],
        "html": [
            "Build a personal portfolio page",
            "Create a multi-page website",
        ],
        "css": [
            "Recreate a website layout from a screenshot",
            "Build a responsive navbar",
            "Create an animated landing page",
        ],
        "node.js": [
            "Build a REST API with Express.js",
            "Build a file upload service",
            "Create a real-time chat server",
        ],
        "aws": [
            "Launch and configure EC2 instances",
            "Set up S3 for static website hosting",
            "Build a serverless API with Lambda",
        ],
        "typescript": [
            "Convert a JavaScript project to TypeScript",
            "Build a typed REST API",
            "Create typed React components",
        ],
        "testing": [
            "Write unit tests for an existing project",
            "Practice TDD on a small feature",
            "Achieve 80%+ test coverage",
        ],
        "linux": [
            "Complete Linux command line challenges daily",
            "Write shell scripts for automation",
            "Set up a Linux server environment",
        ],
    }
    return practice_map.get(skill_key, [
        f"Complete an online course on {skill_key}",
        f"Build a practice project using {skill_key}",
        f"Solve coding challenges related to {skill_key}",
    ])


def _get_projects_for_skill(skill_key: str, target_role: str) -> list[str]:
    """Get project suggestions for a skill, related to the target career."""
    base_projects: dict[str, list[str]] = {
        "python": [
            "Build a REST API with Flask/FastAPI",
            "Create an automation bot for repetitive tasks",
            "Build a data pipeline processing CSV/JSON files",
        ],
        "javascript": [
            "Build a single-page application",
            "Create a browser extension",
            "Build a real-time chat interface",
        ],
        "react": [
            "Build a complete React dashboard connected to a REST API",
            "Create a full-stack app with React + backend",
        ],
        "sql": [
            "Build a reporting dashboard with complex queries",
            "Design and populate a complete database schema",
        ],
        "data structures": [
            "Build a library management system using trees and hash maps",
            "Implement a pathfinding visualizer",
        ],
        "algorithms": [
            "Build a pathfinding visualizer",
            "Implement a sorting algorithm visualizer",
        ],
        "docker": [
            "Build a microservices architecture with Docker Compose",
            "Deploy a containerized application to the cloud",
        ],
        "machine learning": [
            "Build a prediction model and deploy it as an API",
            "Create a recommendation system",
        ],
        "system design": [
            "Design and document a scalable chat system",
            "Build a URL shortener with analytics",
        ],
        "aws": [
            "Deploy a scalable web application on AWS",
            "Build a serverless data processing pipeline",
        ],
    }

    projects = base_projects.get(skill_key, [
        f"Build a portfolio project demonstrating {skill_key} skills",
        f"Contribute to an open-source project using {skill_key}",
    ])

    return projects


def _get_assessment_for_skill(skill_key: str) -> list[str]:
    """Get assessment checklist for a skill."""
    assessment_map: dict[str, list[str]] = {
        "python": [
            "Can write Python scripts independently",
            "Understands OOP concepts",
            "Can work with files and error handling",
            "Can build a REST API",
        ],
        "javascript": [
            "Can manipulate the DOM",
            "Understands async programming",
            "Can work with APIs",
            "Can build interactive web pages",
        ],
        "react": [
            "Can create functional components",
            "Understands props and state",
            "Can use hooks effectively",
            "Can connect to a REST API",
            "Can build a complete React application",
        ],
        "sql": [
            "Can write complex queries with JOINs",
            "Can use aggregation functions",
            "Understands database design",
            "Can optimize query performance",
        ],
        "git": [
            "Can use branching and merging",
            "Can resolve merge conflicts",
            "Can create and manage pull requests",
            "Understands Git workflows",
        ],
        "docker": [
            "Can write Dockerfiles",
            "Can use Docker Compose",
            "Can manage containers and volumes",
            "Can containerize a web application",
        ],
        "data structures": [
            "Can implement common data structures",
            "Understands Big O complexity",
            "Can choose appropriate data structures for problems",
        ],
        "algorithms": [
            "Can implement sorting algorithms",
            "Can solve dynamic programming problems",
            "Can apply graph algorithms",
        ],
    }
    return assessment_map.get(skill_key, [
        f"Can use {skill_key} independently",
        f"Understands core {skill_key} concepts",
        f"Has completed a project using {skill_key}",
    ])


def _format_resources(resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format learning resources with proper rating display."""
    formatted = []
    for r in resources:
        rating = r.get("rating", 3)
        formatted.append({
            "title": r.get("title", ""),
            "provider": r.get("provider", ""),
            "type": r.get("type", "Resource"),
            "level": r.get("level", "Beginner"),
            "url": r.get("url", ""),
            "free": r.get("free", True),
            "rating": rating,
            "rating_stars": "★" * rating + "☆" * (5 - rating),
        })
    return formatted


def _build_reskilling_context(target_role: str, user_skills: list[str]) -> dict[str, Any]:
    """Build reskilling context if user's career is at risk."""
    return {
        "target_role": target_role,
        "transition_type": "skill_enhancement",
        "note": "Completing these recommended skills can improve your alignment with the selected career.",
    }


def generate_reskilling_roadmap(
    resume_text: str,
    current_career: str,
    automation_risk: str,
    recommended_transition: str,
    weekly_hours: int = 8,
) -> dict[str, Any]:
    """Generate a reskilling roadmap for career transition.

    This is used when the user's current career has high automation risk.
    It leverages the AI Career Risk Assessment output to create a
    personalized reskilling plan for the recommended transition career.

    Args:
        resume_text: The user's resume text.
        current_career: The user's current career role.
        automation_risk: The automation risk level (Low/Moderate/High).
        recommended_transition: The recommended target career to transition to.
        weekly_hours: Hours per week the user can commit.

    Returns:
        A structured reskilling roadmap.
    """
    from risk_assessor import analyze_skills_gap

    # Analyze skill gap for the recommended transition career
    gap_result = analyze_skills_gap(resume_text, recommended_transition)

    if "error" in gap_result:
        return {"error": gap_result["error"]}

    # Generate personalized roadmap for the transition career
    roadmap = generate_personalized_roadmap(
        resume_text=resume_text,
        target_role=recommended_transition,
        user_skills=gap_result.get("matched_skills", []),
        missing_skills=gap_result.get("missing_skills", []),
        matched_skills=gap_result.get("matched_skills", []),
        high_priority=gap_result.get("high_priority", []),
        medium_priority=gap_result.get("medium_priority", []),
        low_priority=gap_result.get("low_priority", []),
        weekly_hours=weekly_hours,
    )

    # Add reskilling context
    roadmap["reskilling"] = {
        "current_career": current_career,
        "automation_risk": automation_risk,
        "recommended_transition": recommended_transition,
        "reason": f"Your current career ({current_career}) has {automation_risk.lower()} automation risk. Transitioning to {recommended_transition} can improve your career stability.",
        "skills_to_develop": gap_result.get("missing_skills", []),
        "transferable_skills": gap_result.get("matched_skills", []),
    }

    return roadmap
