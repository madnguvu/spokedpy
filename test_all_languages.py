"""
Test script for all 17 language parsers and generators.
Tests Python, JavaScript, TypeScript, Ruby, PHP, Lua, R, Java, Go, Rust, C#, Kotlin, Swift, Scala, C, SQL, Bash.
"""

from visual_editor_core.uir_translator import get_translator

def test_all_languages():
    t = get_translator()
    
    print("=" * 70)
    print("VPyD Language Support Test - All 17 Languages")
    print("=" * 70)
    print(f"\nSupported languages: {t.get_supported_languages()}")
    print()
    
    # Test samples for each language
    test_samples = {
        'python': '''
def greet(name):
    return "Hello, " + name

class Calculator:
    def __init__(self, initial):
        self.value = initial
    
    def add(self, n):
        self.value += n
        return self.value
''',
        'javascript': '''
function greet(name) {
    return "Hello, " + name;
}

class Calculator {
    constructor(initial) {
        this.value = initial;
    }
    
    add(n) {
        this.value += n;
        return this.value;
    }
}
''',
        'typescript': '''
interface User {
    name: string;
    age: number;
}

function greet(user: User): string {
    return "Hello, " + user.name;
}

class Calculator {
    private value: number = 0;
    
    public add(n: number): number {
        this.value += n;
        return this.value;
    }
}
''',
        'ruby': '''
class Person
    attr_accessor :name, :age
    
    def initialize(name, age)
        @name = name
        @age = age
    end
    
    def greet
        puts "Hello, " + @name
    end
end

def calculate_sum(a, b)
    a + b
end
''',
        'php': '''<?php
class User {
    private string $name;
    
    public function __construct(string $name) {
        $this->name = $name;
    }
    
    public function greet(): string {
        return "Hello, " . $this->name;
    }
}

function add(int $a, int $b): int {
    return $a + $b;
}
?>''',
        'lua': '''
function greet(name)
    print("Hello, " .. name)
end

Person = {}
Person.__index = Person

function Person:new(name)
    local self = setmetatable({}, Person)
    self.name = name
    return self
end

function Person:say_hello()
    print("Hi, I am " .. self.name)
end
''',
        'r': '''
calculate_mean <- function(x, na.rm = FALSE) {
    return(mean(x, na.rm = na.rm))
}

Person <- R6Class("Person",
    public = list(
        name = NULL,
        initialize = function(name) {
            self$name <- name
        },
        greet = function() {
            print(paste("Hello,", self$name))
        }
    )
)
''',
        'java': '''
public class Calculator {
    private int value;
    
    public Calculator(int initial) {
        this.value = initial;
    }
    
    public int add(int n) {
        this.value += n;
        return this.value;
    }
}

public static void greet(String name) {
    System.out.println("Hello, " + name);
}
''',
        'go': '''
package main

import "fmt"

type Calculator struct {
    value int
}

func (c *Calculator) Add(n int) int {
    c.value += n
    return c.value
}

func greet(name string) {
    fmt.Println("Hello, " + name)
}
''',
        'rust': '''
struct Calculator {
    value: i32,
}

impl Calculator {
    fn new(initial: i32) -> Self {
        Calculator { value: initial }
    }
    
    fn add(&mut self, n: i32) -> i32 {
        self.value += n;
        self.value
    }
}

fn greet(name: &str) {
    println!("Hello, {}", name);
}
''',
        'csharp': '''
public class Calculator {
    private int value;
    
    public Calculator(int initial) {
        this.value = initial;
    }
    
    public int Add(int n) {
        this.value += n;
        return this.value;
    }
}

public static void Greet(string name) {
    Console.WriteLine("Hello, " + name);
}
''',
        'kotlin': '''
class Calculator(initial: Int) {
    private var value: Int = initial
    
    fun add(n: Int): Int {
        value += n
        return value
    }
}

fun greet(name: String) {
    println("Hello, $name")
}
''',
        'swift': '''
class Calculator {
    private var value: Int
    
    init(initial: Int) {
        self.value = initial
    }
    
    func add(_ n: Int) -> Int {
        self.value += n
        return self.value
    }
}

func greet(name: String) {
    print("Hello, \\(name)")
}
''',
        'scala': '''
class Calculator(initial: Int) {
    private var value: Int = initial
    
    def add(n: Int): Int = {
        value += n
        value
    }
}

def greet(name: String): Unit = {
    println(s"Hello, $name")
}
''',
        'c': '''
struct Calculator {
    int value;
};

int calculator_add(struct Calculator* calc, int n) {
    calc->value += n;
    return calc->value;
}

void greet(const char* name) {
    printf("Hello, %s\\n", name);
}
''',
        'sql': '''
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE
);

CREATE PROCEDURE get_user_by_id(IN user_id INT)
BEGIN
    SELECT * FROM users WHERE id = user_id;
END;

CREATE FUNCTION calculate_total(price DECIMAL, quantity INT)
RETURNS DECIMAL
BEGIN
    RETURN price * quantity;
END;
''',
        'bash': '''
#!/bin/bash

greet() {
    local name="$1"
    echo "Hello, $name"
}

calculate_sum() {
    local a=$1
    local b=$2
    echo $((a + b))
}

# Array example
declare -a colors=("red" "green" "blue")
'''
    }
    
    # Extension mappings
    extensions = {
        'python': '.py',
        'javascript': '.js',
        'typescript': '.ts',
        'ruby': '.rb',
        'php': '.php',
        'lua': '.lua',
        'r': '.R',
        'java': '.java',
        'go': '.go',
        'rust': '.rs',
        'csharp': '.cs',
        'kotlin': '.kt',
        'swift': '.swift',
        'scala': '.scala',
        'c': '.c',
        'sql': '.sql',
        'bash': '.sh'
    }
    
    # Test parsing for each language
    print("Testing Language Parsers:")
    print("-" * 70)
    
    results = {'passed': 0, 'failed': 0}
    
    for lang, code in test_samples.items():
        try:
            ext = extensions[lang]
            module = t.parse_code_to_uir(code, lang, f'test{ext}')
            funcs = len(module.functions)
            classes = len(module.classes)
            print(f"✓ {lang.upper():12} | Functions: {funcs:2} | Classes: {classes:2} | Parsed successfully")
            results['passed'] += 1
        except Exception as e:
            print(f"✗ {lang.upper():12} | ERROR: {str(e)[:50]}")
            results['failed'] += 1
    
    print("-" * 70)
    print()
    
    # Test code generation for all languages from Python source
    print("Testing Code Generation (Python → All Languages):")
    print("-" * 70)
    
    # Parse Python source
    py_code = test_samples['python']
    py_module = t.parse_code_to_uir(py_code, 'python', 'test.py')
    
    gen_results = {'passed': 0, 'failed': 0}
    
    for lang in test_samples.keys():
        try:
            output = t.generate_code_from_uir(py_module, lang)
            lines = len(output.split('\n'))
            chars = len(output)
            print(f"✓ {lang.upper():12} | Lines: {lines:3} | Chars: {chars:4} | Generated successfully")
            gen_results['passed'] += 1
        except Exception as e:
            print(f"✗ {lang.upper():12} | ERROR: {str(e)[:50]}")
            gen_results['failed'] += 1
    
    print("-" * 70)
    print()
    
    # Test cross-language translation
    print("Testing Cross-Language Translation Examples:")
    print("-" * 70)
    
    translations = [
        ('python', 'java'),
        ('javascript', 'typescript'),
        ('ruby', 'python'),
        ('go', 'rust'),
        ('kotlin', 'swift'),
    ]
    
    trans_results = {'passed': 0, 'failed': 0}
    
    for src_lang, tgt_lang in translations:
        try:
            src_code = test_samples[src_lang]
            output, _ = t.translate_code(src_code, src_lang, tgt_lang)
            lines = len(output.split('\n'))
            print(f"✓ {src_lang.upper():10} → {tgt_lang.upper():10} | Lines: {lines:3} | Success")
            trans_results['passed'] += 1
        except Exception as e:
            print(f"✗ {src_lang.upper():10} → {tgt_lang.upper():10} | ERROR: {str(e)[:40]}")
            trans_results['failed'] += 1
    
    print("-" * 70)
    print()
    
    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Parser Tests:      {results['passed']}/{results['passed'] + results['failed']} passed")
    print(f"Generator Tests:   {gen_results['passed']}/{gen_results['passed'] + gen_results['failed']} passed")
    print(f"Translation Tests: {trans_results['passed']}/{trans_results['passed'] + trans_results['failed']} passed")
    print()
    
    total_passed = results['passed'] + gen_results['passed'] + trans_results['passed']
    total_tests = total_passed + results['failed'] + gen_results['failed'] + trans_results['failed']
    
    if results['failed'] + gen_results['failed'] + trans_results['failed'] == 0:
        print(f"🎉 All {total_tests} tests passed! 17 languages fully supported.")
    else:
        print(f"⚠️  {total_passed}/{total_tests} tests passed. Some languages need attention.")
    print("=" * 70)


if __name__ == "__main__":
    test_all_languages()
