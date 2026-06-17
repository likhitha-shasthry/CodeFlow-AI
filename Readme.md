# CodeFlow AI - README

```html
<!DOCTYPE html>
<html>
<head>
    <title>CodeFlow AI</title>
</head>
<body>

    <h1>CodeFlow AI</h1>

    <h2>Project Overview</h2>
    <p>
        CodeFlow AI is an interactive educational tool that helps students understand
        how Python programs execute internally. Instead of displaying only the final
        output, the system visualizes code execution line by line, tracks variable
        changes, highlights the currently executing statement, and explains program
        behavior in a beginner-friendly manner.
    </p>

    <h2>Features</h2>
    <ul>
        <li>Step-by-step code execution visualization</li>
        <li>Memory panel showing variable updates</li>
        <li>Execution trace using Python tracing mechanisms</li>
        <li>Automatic syntax and runtime error detection</li>
        <li>State table for tracking variable changes</li>
        <li>Play, Pause, Next, Previous, and Reset controls</li>
        <li>Interactive Streamlit-based user interface</li>
    </ul>

    <h2>Technology Stack</h2>
    <ul>
        <li>Python</li>
        <li>Streamlit</li>
        <li>AST (Abstract Syntax Tree)</li>
        <li>sys.settrace()</li>
        <li>HTML & CSS</li>
    </ul>

    <h2>How It Works</h2>
    <ol>
        <li>User enters Python code.</li>
        <li>The system validates syntax using AST parsing.</li>
        <li>The code is compiled and executed safely.</li>
        <li>Execution is traced line by line.</li>
        <li>Local variables are captured after each step.</li>
        <li>The explanation engine generates human-readable descriptions.</li>
        <li>The execution story is displayed through an interactive interface.</li>
    </ol>

    <h2>Project Structure</h2>
    <pre>
CodeFlow-AI/
│
├── app.py
├── requirements.txt
├── README.html
└── assets/
    └── screenshots
    </pre>

    <h2>Installation</h2>
    <pre>
pip install -r requirements.txt
streamlit run app.py
    </pre>

    <h2>Sample Input</h2>
    <pre>
total = 0

for i in range(1, 4):
    total += i

print(total)
    </pre>

    <h2>Sample Output</h2>
    <pre>
Step 1: total = 0
Step 2: Loop starts
Step 3: i = 1, total = 1
Step 4: i = 2, total = 3
Step 5: i = 3, total = 6
Output: 6
    </pre>

    <h2>Future Enhancements</h2>
    <ul>
        <li>Support for multiple programming languages</li>
        <li>AI-generated error explanations</li>
        <li>Personalized learning recommendations</li>
        <li>Faculty analytics dashboard</li>
        <li>Cloud deployment and classroom integration</li>
    </ul>

    <h2>Authors</h2>
    <p>
        Developed as an educational AI project to improve programming
        learning through execution visualization and intelligent explanations.
    </p>

</body>
</html>
```
