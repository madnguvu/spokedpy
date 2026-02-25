"""Load the registry grid with 3 snippets per engine (15 engines × 3 = 45 slots)."""
import requests, json, time

BASE = "http://localhost:5002"

# Engine letter → language name + 3 sample snippets
ENGINES = {
    'a': ('python', [
        ('Fibonacci',     'def fib(n):\n    a,b=0,1\n    for _ in range(n): a,b=b,a+b\n    return a\nprint(fib(10))'),
        ('Prime Sieve',   'def sieve(n):\n    s=set(range(2,n+1))\n    for i in range(2,int(n**0.5)+1):\n        s-=set(range(i*2,n+1,i))\n    return sorted(s)\nprint(sieve(30))'),
        ('Matrix Mult',   'A=[[1,2],[3,4]]\nB=[[5,6],[7,8]]\nC=[[sum(a*b for a,b in zip(r,c)) for c in zip(*B)] for r in A]\nprint(C)'),
    ]),
    'b': ('javascript', [
        ('Hello Node-1 from Node-2 via javascript',   'console.log("Hello from JS engine");'),
        ('Array Map',     'const arr = [1,2,3,4,5];\nconsole.log(arr.map(x => x * x));'),
        ('Fizzbuzz',      'for(let i=1;i<=15;i++) console.log(i%15==0?"FizzBuzz":i%3==0?"Fizz":i%5==0?"Buzz":i);'),
    ]),
    'c': ('typescript', [
        ('Greet',         'const greet = (name: string): string => `Hello, ${name}!`;\nconsole.log(greet("TypeScript"));'),
        ('Sum Array',     'const nums: number[] = [10, 20, 30];\nconsole.log(nums.reduce((a: number, b: number) => a + b, 0));'),
        ('Enum Demo',     'enum Color { Red, Green, Blue }\nconsole.log(Color.Green);'),
    ]),
    'd': ('rust', [
        ('Hello Rust',    'fn main() {\n    println!("Hello from Rust!");\n}'),
        ('Factorial',     'fn factorial(n: u64) -> u64 {\n    if n <= 1 { 1 } else { n * factorial(n-1) }\n}\nfn main() {\n    println!("{}", factorial(10));\n}'),
        ('Fibonacci',     'fn fib(n: u32) -> u64 {\n    let (mut a, mut b) = (0u64, 1u64);\n    for _ in 0..n { let t = a + b; a = b; b = t; }\n    a\n}\nfn main() {\n    println!("{}", fib(20));\n}'),
    ]),
    'e': ('java', [
        ('Hello Java',    'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello from Java!");\n    }\n}'),
        ('Sum',           'public class Main {\n    public static void main(String[] args) {\n        int sum = 0;\n        for(int i=1;i<=100;i++) sum+=i;\n        System.out.println(sum);\n    }\n}'),
        ('Reverse',       'public class Main {\n    public static void main(String[] args) {\n        String s = "Hello";\n        System.out.println(new StringBuilder(s).reverse());\n    }\n}'),
    ]),
    'f': ('swift', [
        ('Hello Swift',   'print("Hello from Swift!")'),
        ('Range Sum',     'let sum = (1...10).reduce(0, +)\nprint(sum)'),
        ('Array Filter',  'let nums = [1,2,3,4,5,6,7,8,9,10]\nprint(nums.filter { $0 % 2 == 0 })'),
    ]),
    'g': ('cpp', [
        ('Hello C++',     '#include <iostream>\nint main() {\n    std::cout << "Hello from C++!" << std::endl;\n    return 0;\n}'),
        ('Factorial',     '#include <iostream>\nint fact(int n) { return n<=1 ? 1 : n*fact(n-1); }\nint main() { std::cout << fact(10) << std::endl; return 0; }'),
        ('Vector Sum',    '#include <iostream>\n#include <vector>\n#include <numeric>\nint main() {\n    std::vector<int> v={1,2,3,4,5};\n    std::cout << std::accumulate(v.begin(),v.end(),0) << std::endl;\n    return 0;\n}'),
    ]),
    'h': ('r', [
        ('Hello R',       'cat("Hello from R!\\n")'),
        ('Mean',          'x <- c(10, 20, 30, 40, 50)\ncat(mean(x), "\\n")'),
        ('Sequence',      'cat(seq(1, 10, by=2), "\\n")'),
    ]),
    'i': ('go', [
        ('Hello Go',      'package main\nimport "fmt"\nfunc main() {\n    fmt.Println("Hello from Go!")\n}'),
        ('Sum',           'package main\nimport "fmt"\nfunc main() {\n    sum := 0\n    for i := 1; i <= 100; i++ { sum += i }\n    fmt.Println(sum)\n}'),
        ('Fibonacci',     'package main\nimport "fmt"\nfunc fib(n int) int {\n    a, b := 0, 1\n    for i := 0; i < n; i++ { a, b = b, a+b }\n    return a\n}\nfunc main() { fmt.Println(fib(10)) }'),
    ]),
    'j': ('ruby', [
        ('Hello Ruby',    'puts "Hello from Ruby!"'),
        ('Array Sum',     'puts [1,2,3,4,5].sum'),
        ('Factorial',     'def fact(n) = n <= 1 ? 1 : n * fact(n-1)\nputs fact(10)'),
    ]),
    'k': ('csharp', [
        ('Hello C#',      'using System;\nclass Program {\n    static void Main() {\n        Console.WriteLine("Hello from C#!");\n    }\n}'),
        ('LINQ Sum',      'using System;\nusing System.Linq;\nclass Program {\n    static void Main() {\n        var nums = Enumerable.Range(1,10);\n        Console.WriteLine(nums.Sum());\n    }\n}'),
        ('Reverse',       'using System;\nclass Program {\n    static void Main() {\n        char[] arr = "Hello".ToCharArray();\n        Array.Reverse(arr);\n        Console.WriteLine(new string(arr));\n    }\n}'),
    ]),
    'l': ('kotlin', [
        ('Hello Kotlin',  'fun main() {\n    println("Hello from Kotlin!")\n}'),
        ('Sum Range',     'fun main() {\n    println((1..100).sum())\n}'),
        ('List Filter',   'fun main() {\n    val nums = listOf(1,2,3,4,5,6,7,8,9,10)\n    println(nums.filter { it % 2 == 0 })\n}'),
    ]),
    'm': ('c', [
        ('Hello C',       '#include <stdio.h>\nint main() {\n    printf("Hello from C!\\n");\n    return 0;\n}'),
        ('Factorial',     '#include <stdio.h>\nint fact(int n) { return n<=1 ? 1 : n*fact(n-1); }\nint main() { printf("%d\\n", fact(10)); return 0; }'),
        ('Sum Array',     '#include <stdio.h>\nint main() {\n    int a[]={1,2,3,4,5}, s=0;\n    for(int i=0;i<5;i++) s+=a[i];\n    printf("%d\\n",s);\n    return 0;\n}'),
    ]),
    'n': ('bash', [
        ('Hello Bash',    'echo "Hello from Bash!"'),
        ('Count',         'for i in $(seq 1 5); do echo "Count: $i"; done'),
        ('Sum',           'sum=0; for i in $(seq 1 10); do sum=$((sum+i)); done; echo $sum'),
    ]),
    'o': ('perl', [
        ('Hello Perl',    'print "Hello from Perl!\\n";'),
        ('Array Sum',     'my @nums = (1..10);\nmy $sum = 0;\n$sum += $_ for @nums;\nprint "$sum\\n";'),
        ('Reverse',       'my $str = "Hello";\nprint scalar reverse($str), "\\n";'),
    ]),
}

def submit(engine_letter, language, code, label):
    """Submit a snippet via the marshal API."""
    resp = requests.post(f"{BASE}/api/marshal", json={
        'engine_letter': engine_letter,
        'language': language,
        'code': code,
        'label': label,
        'auto_promote': True,
        'ttl': 86400,  # 24-hour TTL so they stick around
        'origin': 'api',
        'submitter': 'grid-loader',
        'agent_id': 'load-grid-script',
    })
    return resp.json()

def main():
    print(f"Loading grid: 15 engines x 3 slots = 45 snippets")
    print(f"{'='*60}")
    
    success = 0
    failed = 0
    
    for letter, (lang, snippets) in ENGINES.items():
        for i, (label, code) in enumerate(snippets, 1):
            result = submit(letter, lang, code, label)
            ok = result.get('success', False)
            phase = result.get('phase', '?')
            token = result.get('token', '?')
            addr = result.get('address', '')
            
            status = "OK" if ok else "FAIL"
            if ok:
                success += 1
            else:
                failed += 1
            
            err = result.get('error', '')
            print(f"  [{status}] {letter.upper()}-{lang:12s} slot {i}/3  "
                  f"phase={phase:10s}  token={token}  {err}")
        
    print(f"{'='*60}")
    print(f"Done: {success} promoted, {failed} failed, {success+failed} total")
    
    # Now lock a few slots to test lock persistence
    print(f"\nLocking some slots for persistence test...")
    locks = ['a01', 'b01', 'c01', 'd01', 'e01']
    for addr in locks:
        resp = requests.post(f"{BASE}/api/registry/slot/{addr}/lock",
                             json={'reason': 'Grid loader persistence test'})
        r = resp.json()
        ok = r.get('success', False)
        print(f"  Lock {addr}: {'OK' if ok else 'FAIL'} — {r.get('error','')}")
    
    # Show final state
    print(f"\nFinal matrix state:")
    resp = requests.get(f"{BASE}/api/registry/matrix/enriched")
    matrix = resp.json()
    if matrix.get('success'):
        engines = matrix.get('engines', [])
        # Handle both list-of-dicts and dict-of-dicts formats
        if isinstance(engines, dict):
            engines = list(engines.values())
        for row in engines:
            if isinstance(row, str):
                print(f"  {row}")
                continue
            letter = row.get('letter', '?')
            lang = row.get('language', '?')
            # Slots can be a dict (pos_str → slot_data|None) or a list
            raw_slots = row.get('slots', {})
            if isinstance(raw_slots, dict):
                slot_list = [v for v in raw_slots.values() if v and isinstance(v, dict)]
            else:
                slot_list = [s for s in raw_slots if s and isinstance(s, dict)]
            occupied = len([s for s in slot_list if s.get('node_id')])
            locked_addrs = [s.get('address', '?') for s in slot_list if s.get('locked')]
            lock_str = f"  locked: {locked_addrs}" if locked_addrs else ""
            print(f"  {letter.upper()} {lang:12s}: {occupied} slots occupied{lock_str}")
    
    print(f"\nCheckpoint status:")
    try:
        resp = requests.get(f"{BASE}/api/runtime/state")
        if resp.status_code == 200 and resp.text.strip():
            state = resp.json()
            print(f"  node1 to node2 Has checkpoint: {state.get('has_checkpoint', False)}")
            print(f"  Slots: {state.get('total_slots', 0)}")
            print(f"  Locked: {state.get('locked_slots', 0)}")
        else:
            print(f"  (endpoint returned {resp.status_code}, skipping)")
    except Exception as e:
        print(f"  (checkpoint query failed: {e})")

if __name__ == '__main__':
    main()
