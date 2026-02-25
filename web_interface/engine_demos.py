"""
Polyglot Engine Demo — pre-built code snippets for all available engines.

Provides /api/demos/engine-tabs which returns tab data for every engine
whose toolchain is detected on PATH.  The frontend calls this and feeds
each entry into LiveExecutionPanel.addEngineTab().

Every snippet is a *real*, runnable program that showcases something
interesting in its language — not just "hello world".
"""

import shutil
import json

# ── Toolchain detection ────────────────────────────────────────────────────
TOOLCHAINS = {
    'a': ('python',  'python'),
    'b': ('node',    'javascript'),
    'c': ('ts-node', 'typescript'),     # also check tsx
    'd': ('rustc',   'rust'),
    'e': ('javac',   'java'),
    'f': ('swift',   'swift'),
    'g': ('g++',     'cpp'),
    'h': ('Rscript', 'r'),
    'i': ('go',      'go'),
    'j': ('ruby',    'ruby'),
    'k': ('dotnet',  'csharp'),
    'l': ('kotlinc', 'kotlin'),
    'm': ('gcc',     'c'),
    'n': ('bash',    'bash'),
}

# Extra fallback checks
TOOLCHAIN_ALTS = {
    'c': ['tsx'],
    'g': ['clang++', 'c++'],
    'm': ['cc'],
    'n': ['sh'],
}


def _is_available(letter: str) -> bool:
    """Check if the primary or alternative toolchain binary is on PATH."""
    primary = TOOLCHAINS[letter][0]
    if shutil.which(primary):
        return True
    for alt in TOOLCHAIN_ALTS.get(letter, []):
        if shutil.which(alt):
            return True
    return False


def get_available_engines() -> list:
    """Return list of dicts for every engine with a toolchain on PATH."""
    available = []
    for letter in sorted(TOOLCHAINS.keys()):
        cmd, lang = TOOLCHAINS[letter]
        available.append({
            'engine_letter': letter,
            'language': lang,
            'toolchain': cmd,
            'available': _is_available(letter),
        })
    return available


# ── Demo code snippets ─────────────────────────────────────────────────────
# Each snippet is designed to be self-contained, print interesting output,
# and demonstrate a real capability of the language.

DEMO_SNIPPETS = {}

# ─── Python (a) ───────────────────────────────────────────────────────────
DEMO_SNIPPETS['a'] = {
    'label': 'Python — Data Pipeline',
    'code': r'''# ━━━ VPyD Python Engine Demo ━━━
# Real data pipeline: generate → transform → aggregate → report

import json
import math
from collections import Counter
from datetime import datetime

# 1) Generate sensor data
sensors = []
for i in range(50):
    temp = 20 + 10 * math.sin(i * 0.3) + (i % 7) * 0.5
    humidity = 45 + 15 * math.cos(i * 0.2)
    sensors.append({
        'id': f'sensor-{i:03d}',
        'temp_c': round(temp, 2),
        'humidity': round(humidity, 1),
        'zone': ['North', 'South', 'East', 'West'][i % 4],
    })

# 2) Transform: flag anomalies (temp > 28°C)
for s in sensors:
    s['anomaly'] = s['temp_c'] > 28.0

# 3) Aggregate by zone
zone_stats = {}
for s in sensors:
    z = s['zone']
    if z not in zone_stats:
        zone_stats[z] = {'temps': [], 'anomalies': 0, 'count': 0}
    zone_stats[z]['temps'].append(s['temp_c'])
    zone_stats[z]['anomalies'] += int(s['anomaly'])
    zone_stats[z]['count'] += 1

# 4) Report
print("╔══════════════════════════════════════════════════╗")
print("║       VPyD Sensor Data Pipeline Report          ║")
print("╠══════════════════════════════════════════════════╣")
for zone in sorted(zone_stats):
    st = zone_stats[zone]
    avg = sum(st['temps']) / len(st['temps'])
    mx  = max(st['temps'])
    mn  = min(st['temps'])
    print(f"║  {zone:6s} │ avg {avg:5.1f}°C │ "
          f"range [{mn:5.1f}, {mx:5.1f}] │ ⚠ {st['anomalies']}")
print("╠══════════════════════════════════════════════════╣")

total_anomalies = sum(s['anomaly'] for s in sensors)
print(f"║  Total sensors: {len(sensors)}  │  Anomalies: {total_anomalies}")
print(f"║  Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("╚══════════════════════════════════════════════════╝")

# Variables available for inspection
pipeline_result = {
    'total_sensors': len(sensors),
    'zones': list(zone_stats.keys()),
    'total_anomalies': total_anomalies,
}
''',
}

# ─── JavaScript (b) ───────────────────────────────────────────────────────
DEMO_SNIPPETS['b'] = {
    'label': 'JavaScript — Async Task Scheduler',
    'code': r'''// ━━━ VPyD JavaScript Engine Demo ━━━
// Async task scheduler with priority queue and execution timeline

class TaskScheduler {
    constructor() {
        this.queue = [];
        this.results = [];
        this.startTime = Date.now();
    }

    addTask(name, priority, durationMs, fn) {
        this.queue.push({ name, priority, durationMs, fn });
        this.queue.sort((a, b) => b.priority - a.priority);
    }

    async run() {
        console.log("┌─────────────────────────────────────────┐");
        console.log("│   VPyD Task Scheduler — Execution Log   │");
        console.log("├─────────────────────────────────────────┤");

        for (const task of this.queue) {
            const t0 = Date.now() - this.startTime;
            process.stdout.write(`│  ▶ [P${task.priority}] ${task.name.padEnd(20)}`);

            const result = await task.fn();

            const t1 = Date.now() - this.startTime;
            console.log(` ✓ ${(t1 - t0)}ms`);
            this.results.push({ name: task.name, result, elapsed: t1 - t0 });
        }

        console.log("├─────────────────────────────────────────┤");
        console.log(`│  Total: ${this.results.length} tasks in ${Date.now() - this.startTime}ms`);
        console.log("└─────────────────────────────────────────┘");
    }
}

// Simulate async work
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

const scheduler = new TaskScheduler();

scheduler.addTask("Parse config", 10, 50, async () => {
    await sleep(30);
    return { format: "JSON", keys: 12 };
});

scheduler.addTask("Validate schema", 9, 40, async () => {
    await sleep(20);
    return { valid: true, warnings: 0 };
});

scheduler.addTask("Transform data", 8, 80, async () => {
    const data = Array.from({ length: 1000 }, (_, i) => i * i);
    await sleep(40);
    return { rows: data.length, checksum: data.reduce((a, b) => a + b, 0) };
});

scheduler.addTask("Generate report", 5, 60, async () => {
    await sleep(25);
    return { pages: 3, format: "HTML" };
});

scheduler.addTask("Send notification", 3, 30, async () => {
    await sleep(15);
    return { channel: "websocket", sent: true };
});

scheduler.run().then(() => {
    console.log("\n📊 Results Summary:");
    scheduler.results.forEach(r => {
        console.log(`   ${r.name}: ${JSON.stringify(r.result)}`);
    });
});
''',
}

# ─── TypeScript (c) ────────────────────────────────────────────────────────
DEMO_SNIPPETS['c'] = {
    'label': 'TypeScript — Type-Safe State Machine',
    'code': r'''// ━━━ VPyD TypeScript Engine Demo ━━━
// Type-safe finite state machine with transition validation

type State = "idle" | "loading" | "processing" | "success" | "error";
type Event = "start" | "data_ready" | "process" | "complete" | "fail" | "reset";

interface Transition {
    from: State;
    event: Event;
    to: State;
    action?: string;
}

const transitions: Transition[] = [
    { from: "idle",       event: "start",      to: "loading",    action: "initConnection" },
    { from: "loading",    event: "data_ready",  to: "processing", action: "parseData" },
    { from: "processing", event: "complete",    to: "success",    action: "saveResults" },
    { from: "processing", event: "fail",        to: "error",      action: "logError" },
    { from: "loading",    event: "fail",        to: "error",      action: "logError" },
    { from: "error",      event: "reset",       to: "idle",       action: "cleanup" },
    { from: "success",    event: "reset",       to: "idle",       action: "cleanup" },
];

class StateMachine {
    private current: State = "idle";
    private history: { state: State; event: Event; action?: string; ts: number }[] = [];

    transition(event: Event): boolean {
        const t = transitions.find(tr => tr.from === this.current && tr.event === event);
        if (!t) {
            console.log(`  ✗ Invalid: ${this.current} + ${event}`);
            return false;
        }
        this.history.push({ state: this.current, event, action: t.action, ts: Date.now() });
        console.log(`  ${this.current} ──[${event}]──▶ ${t.to}${t.action ? ` (${t.action})` : ""}`);
        this.current = t.to;
        return true;
    }

    getState(): State { return this.current; }
    getHistory() { return this.history; }
}

console.log("┌──────────────────────────────────────────────┐");
console.log("│  VPyD TypeScript State Machine Demo          │");
console.log("├──────────────────────────────────────────────┤");

const sm = new StateMachine();

// Happy path
console.log("\n  ── Happy Path ──");
sm.transition("start");
sm.transition("data_ready");
sm.transition("complete");
sm.transition("reset");

// Error path
console.log("\n  ── Error Path ──");
sm.transition("start");
sm.transition("fail");
sm.transition("reset");

// Invalid transition
console.log("\n  ── Invalid Transition ──");
sm.transition("complete");  // Can't complete from idle

console.log(`\n  Final state: ${sm.getState()}`);
console.log(`  Transitions recorded: ${sm.getHistory().length}`);
console.log("└──────────────────────────────────────────────┘");
''',
}

# ─── Java (e) ──────────────────────────────────────────────────────────────
DEMO_SNIPPETS['e'] = {
    'label': 'Java — Concurrent Word Frequency',
    'code': r'''// ━━━ VPyD Java Engine Demo ━━━
// Concurrent word frequency analysis with streams

import java.util.*;
import java.util.stream.*;
import java.util.concurrent.*;

public class Main {
    public static void main(String[] args) {
        String[] documents = {
            "The visual editor transforms code into beautiful node graphs that flow like water",
            "Each engine in the polyglot runtime executes code in its native language environment",
            "Python handles data science while JavaScript manages the interactive frontend layer",
            "Rust provides memory safety and performance for system level computations in the pipeline",
            "The execution matrix coordinates all fourteen engines running simultaneously in harmony",
            "Type safe languages like TypeScript and Java catch errors before runtime execution begins",
            "Go excels at concurrent operations with goroutines handling thousands of parallel tasks",
            "The visual node graph makes complex data pipelines intuitive and easy to understand"
        };

        System.out.println("╔══════════════════════════════════════════════╗");
        System.out.println("║   VPyD Java — Concurrent Word Frequency     ║");
        System.out.println("╠══════════════════════════════════════════════╣");

        // Parallel stream word frequency
        Map<String, Long> freq = Arrays.stream(documents)
            .parallel()
            .flatMap(doc -> Arrays.stream(doc.toLowerCase().split("\\s+")))
            .filter(w -> w.length() > 3)
            .collect(Collectors.groupingBy(w -> w, Collectors.counting()));

        // Top 15 words
        List<Map.Entry<String, Long>> top = freq.entrySet().stream()
            .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
            .limit(15)
            .collect(Collectors.toList());

        long maxCount = top.get(0).getValue();
        for (Map.Entry<String, Long> entry : top) {
            int barLen = (int)(entry.getValue() * 30 / maxCount);
            String bar = "█".repeat(barLen);
            System.out.printf("║  %-12s %2d │ %s%n", entry.getKey(), entry.getValue(), bar);
        }

        System.out.println("╠══════════════════════════════════════════════╣");
        System.out.printf("║  Documents: %d │ Unique words: %d%n", documents.length, freq.size());
        System.out.printf("║  Total tokens: %d%n",
            Arrays.stream(documents).mapToInt(d -> d.split("\\s+").length).sum());
        System.out.println("╚══════════════════════════════════════════════╝");
    }
}
''',
}

# ─── Go (i) ────────────────────────────────────────────────────────────────
DEMO_SNIPPETS['i'] = {
    'label': 'Go — Concurrent Prime Sieve',
    'code': r'''// ━━━ VPyD Go Engine Demo ━━━
// Concurrent prime sieve using goroutines and channels

package main

import (
	"fmt"
	"math"
	"sync"
	"time"
)

func sieveSegment(lo, hi int, primes []int, results chan<- []int, wg *sync.WaitGroup) {
	defer wg.Done()
	size := hi - lo
	composite := make([]bool, size)

	for _, p := range primes {
		start := ((lo + p - 1) / p) * p
		if start < p*p {
			start = p * p
		}
		for j := start; j < hi; j += p {
			composite[j-lo] = true
		}
	}

	var segment []int
	for i := 0; i < size; i++ {
		if !composite[i] && (lo+i) >= 2 {
			segment = append(segment, lo+i)
		}
	}
	results <- segment
}

func main() {
	fmt.Println("┌────────────────────────────────────────────┐")
	fmt.Println("│  VPyD Go — Concurrent Segmented Prime Sieve│")
	fmt.Println("├────────────────────────────────────────────┤")

	const limit = 100_000
	start := time.Now()

	// Step 1: small primes via simple sieve
	sqrtLimit := int(math.Sqrt(float64(limit))) + 1
	isComposite := make([]bool, sqrtLimit)
	var smallPrimes []int
	for i := 2; i < sqrtLimit; i++ {
		if !isComposite[i] {
			smallPrimes = append(smallPrimes, i)
			for j := i * i; j < sqrtLimit; j += i {
				isComposite[j] = true
			}
		}
	}

	// Step 2: segment the range into chunks, sieve concurrently
	const segSize = 10_000
	var wg sync.WaitGroup
	results := make(chan []int, limit/segSize+1)

	for lo := sqrtLimit; lo < limit; lo += segSize {
		hi := lo + segSize
		if hi > limit {
			hi = limit
		}
		wg.Add(1)
		go sieveSegment(lo, hi, smallPrimes, results, &wg)
	}

	go func() {
		wg.Wait()
		close(results)
	}()

	allPrimes := append([]int{}, smallPrimes...)
	for seg := range results {
		allPrimes = append(allPrimes, seg...)
	}

	elapsed := time.Since(start)

	fmt.Printf("│  Primes up to %d: %d found\n", limit, len(allPrimes))
	fmt.Printf("│  Computed in: %v\n", elapsed)
	fmt.Println("│")

	// Show distribution by decade
	fmt.Println("│  Distribution (primes per 10k range):")
	for bucket := 0; bucket*10000 < limit; bucket++ {
		lo := bucket * 10000
		hi := lo + 10000
		count := 0
		for _, p := range allPrimes {
			if p >= lo && p < hi {
				count++
			}
		}
		bar := ""
		for i := 0; i < count/50; i++ {
			bar += "█"
		}
		fmt.Printf("│  %6d-%6d: %4d %s\n", lo, hi, count, bar)
	}

	fmt.Printf("│\n│  Largest prime found: %d\n", allPrimes[len(allPrimes)-1])
	fmt.Println("└────────────────────────────────────────────┘")
}
''',
}

# ─── C# (k) ───────────────────────────────────────────────────────────────
DEMO_SNIPPETS['k'] = {
    'label': 'C# — LINQ Analytics Engine',
    'code': r'''// ━━━ VPyD C# Engine Demo ━━━
// LINQ-powered analytics engine with pattern matching

using System;
using System.Linq;
using System.Collections.Generic;

class Program
{
    record Transaction(string Id, string Category, double Amount, DateTime Date, string Status);

    static void Main()
    {
        var rng = new Random(42);
        var categories = new[] { "Electronics", "Books", "Clothing", "Food", "Services" };
        var statuses = new[] { "completed", "completed", "completed", "pending", "refunded" };

        // Generate 200 transactions
        var transactions = Enumerable.Range(1, 200).Select(i => new Transaction(
            Id: $"TXN-{i:D4}",
            Category: categories[rng.Next(categories.Length)],
            Amount: Math.Round(rng.NextDouble() * 500 + 5, 2),
            Date: DateTime.Now.AddDays(-rng.Next(90)),
            Status: statuses[rng.Next(statuses.Length)]
        )).ToList();

        Console.WriteLine("╔═══════════════════════════════════════════════╗");
        Console.WriteLine("║   VPyD C# — LINQ Analytics Engine            ║");
        Console.WriteLine("╠═══════════════════════════════════════════════╣");

        // Category breakdown with LINQ
        var byCategory = transactions
            .Where(t => t.Status == "completed")
            .GroupBy(t => t.Category)
            .Select(g => new {
                Category = g.Key,
                Count = g.Count(),
                Total = g.Sum(t => t.Amount),
                Avg = g.Average(t => t.Amount),
                Max = g.Max(t => t.Amount)
            })
            .OrderByDescending(x => x.Total);

        foreach (var cat in byCategory)
        {
            int bar = (int)(cat.Total / 100);
            Console.WriteLine($"║  {cat.Category,-12} │ {cat.Count,3} txns │ ${cat.Total,8:F2} │ avg ${cat.Avg,6:F2} │ {"█".PadRight(bar, '█')}");
        }

        Console.WriteLine("╠═══════════════════════════════════════════════╣");

        // Status summary using pattern matching
        var statusSummary = transactions
            .GroupBy(t => t.Status)
            .Select(g => (Status: g.Key, Count: g.Count(), Total: g.Sum(t => t.Amount)));

        foreach (var s in statusSummary)
        {
            string icon = s.Status switch
            {
                "completed" => "✅",
                "pending"   => "⏳",
                "refunded"  => "↩️ ",
                _           => "❓"
            };
            Console.WriteLine($"║  {icon} {s.Status,-10} │ {s.Count,3} │ ${s.Total,9:F2}");
        }

        var grandTotal = transactions.Where(t => t.Status == "completed").Sum(t => t.Amount);
        Console.WriteLine("╠═══════════════════════════════════════════════╣");
        Console.WriteLine($"║  Revenue: ${grandTotal:F2}  │  Transactions: {transactions.Count}");
        Console.WriteLine("╚═══════════════════════════════════════════════╝");
    }
}
''',
}

# ─── Bash (n) ──────────────────────────────────────────────────────────────
DEMO_SNIPPETS['n'] = {
    'label': 'Bash — System Profiler',
    'code': r'''#!/bin/bash
# ━━━ VPyD Bash Engine Demo ━━━
# System profiler — gathers real machine info

echo "┌─────────────────────────────────────────────┐"
echo "│   VPyD Bash — System Profiler               │"
echo "├─────────────────────────────────────────────┤"

# OS Info
if [ -f /etc/os-release ]; then
    OS_NAME=$(. /etc/os-release && echo "$PRETTY_NAME")
elif command -v uname &>/dev/null; then
    OS_NAME=$(uname -s -r)
else
    OS_NAME="Unknown"
fi
echo "│  OS:        $OS_NAME"

# Hostname
echo "│  Hostname:  $(hostname 2>/dev/null || echo 'N/A')"

# Shell
echo "│  Shell:     $BASH_VERSION"

# Date
echo "│  Date:      $(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo 'N/A')"

# CPU
if command -v nproc &>/dev/null; then
    echo "│  CPU cores: $(nproc)"
elif command -v sysctl &>/dev/null; then
    echo "│  CPU cores: $(sysctl -n hw.ncpu 2>/dev/null || echo 'N/A')"
fi

# Memory (cross-platform)
if command -v free &>/dev/null; then
    MEM=$(free -h 2>/dev/null | awk '/Mem:/{print $2}')
    echo "│  Memory:    $MEM"
fi

# Disk
if command -v df &>/dev/null; then
    DISK=$(df -h / 2>/dev/null | awk 'NR==2{printf "%s used of %s (%s)", $3, $2, $5}')
    echo "│  Disk /:    $DISK"
fi

echo "├─────────────────────────────────────────────┤"

# Environment scan
echo "│  Language runtimes found:"
for cmd in python3 python node go javac rustc ruby dotnet gcc g++ bash; do
    if command -v "$cmd" &>/dev/null; then
        VER=$($cmd --version 2>&1 | head -n1 | cut -c1-40)
        printf "│    ✓ %-8s %s\n" "$cmd" "$VER"
    fi
done

echo "├─────────────────────────────────────────────┤"

# Quick benchmark: count to 100000
START=$(date +%s%N 2>/dev/null || echo 0)
SUM=0
for i in $(seq 1 1000); do
    SUM=$((SUM + i))
done
END=$(date +%s%N 2>/dev/null || echo 0)

if [ "$START" != "0" ] && [ "$END" != "0" ]; then
    ELAPSED=$(( (END - START) / 1000000 ))
    echo "│  Benchmark: sum(1..1000) = $SUM in ${ELAPSED}ms"
else
    echo "│  Benchmark: sum(1..1000) = $SUM"
fi

echo "└─────────────────────────────────────────────┘"
''',
}

# ─── Rust (d) — included even if not installed ─────────────────────────────
DEMO_SNIPPETS['d'] = {
    'label': 'Rust — Iterator & Ownership Demo',
    'code': r'''// ━━━ VPyD Rust Engine Demo ━━━
// Showcases iterators, ownership, pattern matching, and zero-cost abstractions

use std::collections::HashMap;

fn analyze_text(text: &str) -> HashMap<&str, usize> {
    text.split_whitespace()
        .filter(|w| w.len() > 3)
        .fold(HashMap::new(), |mut acc, word| {
            *acc.entry(word).or_insert(0) += 1;
            acc
        })
}

fn fibonacci(n: usize) -> Vec<u64> {
    let mut fib = vec![0u64, 1];
    for i in 2..n {
        let next = fib[i - 1] + fib[i - 2];
        fib.push(next);
    }
    fib
}

fn main() {
    println!("┌──────────────────────────────────────────────┐");
    println!("│  VPyD Rust — Iterator & Ownership Demo       │");
    println!("├──────────────────────────────────────────────┤");

    // Fibonacci with iterators
    let fibs = fibonacci(20);
    let fib_sum: u64 = fibs.iter().sum();
    println!("│  Fibonacci(20): {:?}", &fibs[..10]);
    println!("│  Sum of first 20: {}", fib_sum);

    // Text analysis with zero-copy slices
    let text = "the visual editor transforms code into node graphs \
                the execution matrix coordinates engines running code \
                the polyglot runtime handles multiple languages at once";

    let freq = analyze_text(text);
    let mut sorted: Vec<_> = freq.iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(a.1));

    println!("│");
    println!("│  Word frequencies (top 8):");
    for (word, count) in sorted.iter().take(8) {
        let bar: String = "█".repeat(**count * 5);
        println!("│    {:12} {:>2} {}", word, count, bar);
    }

    // Pattern matching
    println!("│");
    let values: Vec<Option<i32>> = vec![Some(42), None, Some(7), None, Some(13)];
    let extracted: Vec<i32> = values.iter().filter_map(|v| *v).collect();
    println!("│  Pattern match filter: {:?} → {:?}", values, extracted);

    println!("│  Sum of Some values: {}", extracted.iter().sum::<i32>());
    println!("└──────────────────────────────────────────────┘");
}
''',
}

# ─── C++ (g) ──────────────────────────────────────────────────────────────
DEMO_SNIPPETS['g'] = {
    'label': 'C++ — STL Algorithms Showcase',
    'code': r'''// ━━━ VPyD C++ Engine Demo ━━━
#include <iostream>
#include <vector>
#include <algorithm>
#include <numeric>
#include <map>
#include <cmath>
#include <iomanip>

int main() {
    std::cout << "┌──────────────────────────────────────────────┐\n";
    std::cout << "│  VPyD C++ — STL Algorithms Showcase          │\n";
    std::cout << "├──────────────────────────────────────────────┤\n";

    // Generate data
    std::vector<double> data(50);
    for (int i = 0; i < 50; i++)
        data[i] = 10.0 + 8.0 * sin(i * 0.4) + (i % 5) * 1.5;

    // Stats
    double sum = std::accumulate(data.begin(), data.end(), 0.0);
    double mean = sum / data.size();
    double sq_sum = std::inner_product(data.begin(), data.end(), data.begin(), 0.0);
    double stdev = std::sqrt(sq_sum / data.size() - mean * mean);
    auto [mn, mx] = std::minmax_element(data.begin(), data.end());

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "│  Data points: " << data.size() << "\n";
    std::cout << "│  Mean: " << mean << "  StdDev: " << stdev << "\n";
    std::cout << "│  Range: [" << *mn << ", " << *mx << "]\n";

    // Histogram
    std::cout << "│\n│  Histogram:\n";
    std::map<int, int> hist;
    for (double v : data) hist[static_cast<int>(v)]++;
    for (auto& [val, cnt] : hist) {
        std::cout << "│    " << std::setw(3) << val << " │ ";
        for (int i = 0; i < cnt; i++) std::cout << "█";
        std::cout << " " << cnt << "\n";
    }

    // Partition
    auto mid = std::partition(data.begin(), data.end(),
                              [&](double v) { return v > mean; });
    int above = std::distance(data.begin(), mid);
    std::cout << "│\n│  Above mean: " << above << "  Below: " << (data.size() - above) << "\n";
    std::cout << "└──────────────────────────────────────────────┘\n";
    return 0;
}
''',
}

# ─── C (m) ─────────────────────────────────────────────────────────────────
DEMO_SNIPPETS['m'] = {
    'label': 'C — Memory & Pointers Demo',
    'code': r'''/* ━━━ VPyD C Engine Demo ━━━ */
/* Dynamic array, pointer arithmetic, manual memory management */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

typedef struct {
    double *data;
    int size;
    int capacity;
} DynArray;

DynArray* dynarray_new(int cap) {
    DynArray *a = malloc(sizeof(DynArray));
    a->data = malloc(cap * sizeof(double));
    a->size = 0;
    a->capacity = cap;
    return a;
}

void dynarray_push(DynArray *a, double val) {
    if (a->size >= a->capacity) {
        a->capacity *= 2;
        a->data = realloc(a->data, a->capacity * sizeof(double));
    }
    a->data[a->size++] = val;
}

void dynarray_free(DynArray *a) {
    free(a->data);
    free(a);
}

int main() {
    printf("┌──────────────────────────────────────────────┐\n");
    printf("│  VPyD C — Dynamic Array & Statistics         │\n");
    printf("├──────────────────────────────────────────────┤\n");

    DynArray *arr = dynarray_new(4);

    for (int i = 0; i < 40; i++) {
        double val = 20.0 + 10.0 * sin(i * 0.3) + (i % 3) * 2.0;
        dynarray_push(arr, val);
    }

    printf("│  Array size: %d  capacity: %d\n", arr->size, arr->capacity);

    /* Stats via pointer arithmetic */
    double sum = 0, min = arr->data[0], max = arr->data[0];
    double *ptr = arr->data;
    for (int i = 0; i < arr->size; i++, ptr++) {
        sum += *ptr;
        if (*ptr < min) min = *ptr;
        if (*ptr > max) max = *ptr;
    }
    double mean = sum / arr->size;

    double var_sum = 0;
    for (int i = 0; i < arr->size; i++) {
        double d = arr->data[i] - mean;
        var_sum += d * d;
    }
    double stdev = sqrt(var_sum / arr->size);

    printf("│  Mean:   %.2f\n", mean);
    printf("│  StdDev: %.2f\n", stdev);
    printf("│  Range:  [%.2f, %.2f]\n", min, max);

    /* Histogram */
    printf("│\n│  Histogram:\n");
    int buckets[6] = {0};
    for (int i = 0; i < arr->size; i++) {
        int b = (int)((arr->data[i] - min) / ((max - min + 0.01) / 5));
        if (b > 4) b = 4;
        buckets[b]++;
    }
    for (int b = 0; b < 5; b++) {
        double lo = min + b * (max - min) / 5;
        double hi = lo + (max - min) / 5;
        printf("│  %5.1f-%5.1f │ ", lo, hi);
        for (int j = 0; j < buckets[b]; j++) printf("█");
        printf(" %d\n", buckets[b]);
    }

    dynarray_free(arr);
    printf("│\n│  Memory freed. No leaks.\n");
    printf("└──────────────────────────────────────────────┘\n");
    return 0;
}
''',
}

# ─── Ruby (j) ─────────────────────────────────────────────────────────────
DEMO_SNIPPETS['j'] = {
    'label': 'Ruby — Metaprogramming Demo',
    'code': r'''# ━━━ VPyD Ruby Engine Demo ━━━
# Metaprogramming, blocks, and enumerable magic

class DataPipeline
  attr_reader :steps, :data

  def initialize(data)
    @data = data
    @steps = []
  end

  def transform(name, &block)
    @steps << name
    @data = @data.map(&block)
    self
  end

  def filter(name, &block)
    @steps << name
    @data = @data.select(&block)
    self
  end

  def aggregate(name)
    @steps << name
    yield @data
    self
  end
end

puts "┌──────────────────────────────────────────────┐"
puts "│  VPyD Ruby — Metaprogramming Pipeline        │"
puts "├──────────────────────────────────────────────┤"

# Generate data
data = (1..30).map { |i| { id: i, value: (Math.sin(i * 0.4) * 50 + 50).round(1), tag: %w[alpha beta gamma][i % 3] } }

pipeline = DataPipeline.new(data)
  .transform("square values") { |r| r.merge(value: (r[:value] ** 0.5 * 10).round(1)) }
  .filter("keep > 50") { |r| r[:value] > 50 }
  .transform("add label") { |r| r.merge(label: "#{r[:tag]}-#{r[:id]}") }

puts "│  Pipeline steps: #{pipeline.steps.join(' → ')}"
puts "│  Records remaining: #{pipeline.data.size}"
puts "│"

# Group by tag
groups = pipeline.data.group_by { |r| r[:tag] }
groups.each do |tag, records|
  avg = (records.sum { |r| r[:value] } / records.size.to_f).round(1)
  bar = "█" * (avg / 5).to_i
  puts "│  #{tag.ljust(6)} │ #{records.size.to_s.rjust(2)} records │ avg #{avg.to_s.rjust(5)} │ #{bar}"
end

puts "│"
total = pipeline.data.sum { |r| r[:value] }.round(1)
puts "│  Total value: #{total}"
puts "└──────────────────────────────────────────────┘"
''',
}

# ─── R (h) ─────────────────────────────────────────────────────────────────
DEMO_SNIPPETS['h'] = {
    'label': 'R — Statistical Analysis',
    'code': r'''# ━━━ VPyD R Engine Demo ━━━
# Statistical analysis and visualization (text-based)

cat("┌──────────────────────────────────────────────┐\n")
cat("│  VPyD R — Statistical Analysis               │\n")
cat("├──────────────────────────────────────────────┤\n")

set.seed(42)

# Generate two groups
group_a <- rnorm(100, mean = 50, sd = 10)
group_b <- rnorm(100, mean = 55, sd = 12)

# Summary statistics
cat(sprintf("│  Group A: mean=%.2f sd=%.2f median=%.2f\n",
    mean(group_a), sd(group_a), median(group_a)))
cat(sprintf("│  Group B: mean=%.2f sd=%.2f median=%.2f\n",
    mean(group_b), sd(group_b), median(group_b)))

# T-test
test <- t.test(group_a, group_b)
cat(sprintf("│\n│  T-test: t=%.3f  p=%.4f  df=%.1f\n",
    test$statistic, test$p.value, test$parameter))
cat(sprintf("│  Significant (α=0.05): %s\n",
    ifelse(test$p.value < 0.05, "YES ✓", "NO")))

# Correlation
combined <- c(group_a, group_b)
noise <- combined + rnorm(200, 0, 5)
cor_val <- cor(combined, noise)
cat(sprintf("│\n│  Correlation (data vs noisy): %.4f\n", cor_val))

# Text histogram
cat("│\n│  Distribution (Group A):\n")
breaks <- seq(floor(min(group_a)/5)*5, ceiling(max(group_a)/5)*5, by=5)
h <- hist(group_a, breaks=breaks, plot=FALSE)
for (i in seq_along(h$counts)) {
    bar <- paste(rep("█", h$counts[i] %/% 2), collapse="")
    cat(sprintf("│  %5.0f-%5.0f │ %s %d\n",
        h$breaks[i], h$breaks[i+1], bar, h$counts[i]))
}

# Linear model
x <- 1:100
y <- 2.5 * x + rnorm(100, 0, 15)
model <- lm(y ~ x)
cat(sprintf("│\n│  Linear Model: y = %.2fx + %.2f  (R²=%.3f)\n",
    coef(model)[2], coef(model)[1], summary(model)$r.squared))

cat("└──────────────────────────────────────────────┘\n")
''',
}

# ─── Kotlin (l) ────────────────────────────────────────────────────────────
DEMO_SNIPPETS['l'] = {
    'label': 'Kotlin — Functional Collections',
    'code': r'''// ━━━ VPyD Kotlin Engine Demo ━━━
// Functional collection processing with data classes

data class Product(val name: String, val category: String, val price: Double, val stock: Int)

fun main() {
    println("┌──────────────────────────────────────────────┐")
    println("│  VPyD Kotlin — Functional Collections        │")
    println("├──────────────────────────────────────────────┤")

    val products = listOf(
        Product("Laptop", "Electronics", 999.99, 15),
        Product("Keyboard", "Electronics", 79.99, 42),
        Product("Mouse", "Electronics", 29.99, 88),
        Product("Desk Lamp", "Office", 45.50, 33),
        Product("Notebook", "Office", 12.99, 150),
        Product("Pen Set", "Office", 8.99, 200),
        Product("Headphones", "Electronics", 149.99, 27),
        Product("Monitor", "Electronics", 449.99, 12),
        Product("Chair", "Furniture", 299.99, 8),
        Product("Bookshelf", "Furniture", 189.99, 5)
    )

    // Category analysis with functional chains
    val byCat = products
        .groupBy { it.category }
        .mapValues { (_, items) ->
            mapOf(
                "count" to items.size,
                "totalValue" to items.sumOf { it.price * it.stock },
                "avgPrice" to items.map { it.price }.average()
            )
        }

    byCat.forEach { (cat, stats) ->
        val value = stats["totalValue"] as Double
        val bar = "█".repeat((value / 1000).toInt().coerceAtMost(25))
        println("│  ${cat.padEnd(12)} │ ${(stats["count"] as Int).toString().padStart(2)} items │ $${"%,.0f".format(value).padStart(8)} │ $bar")
    }

    println("│")
    val totalInventoryValue = products.sumOf { it.price * it.stock }
    val mostExpensive = products.maxByOrNull { it.price }
    val mostStocked = products.maxByOrNull { it.stock }

    println("│  Total inventory value: $${"%,.2f".format(totalInventoryValue)}")
    println("│  Most expensive: ${mostExpensive?.name} ($${mostExpensive?.price})")
    println("│  Most stocked:   ${mostStocked?.name} (${mostStocked?.stock} units)")
    println("└──────────────────────────────────────────────┘")
}
''',
}

# ─── Swift (f) ─────────────────────────────────────────────────────────────
DEMO_SNIPPETS['f'] = {
    'label': 'Swift — Protocol-Oriented Design',
    'code': r'''// ━━━ VPyD Swift Engine Demo ━━━
// Protocol-oriented design with generics

protocol Measurable {
    var value: Double { get }
}

struct Temperature: Measurable, CustomStringConvertible {
    let value: Double
    let unit: String
    var description: String { "\(String(format: "%.1f", value))°\(unit)" }
}

struct Statistics<T: Measurable> {
    let data: [T]

    var mean: Double { data.map(\.value).reduce(0, +) / Double(data.count) }
    var min: Double { data.map(\.value).min() ?? 0 }
    var max: Double { data.map(\.value).max() ?? 0 }
    var stddev: Double {
        let m = mean
        let variance = data.map { ($0.value - m) * ($0.value - m) }.reduce(0, +) / Double(data.count)
        return variance.squareRoot()
    }
}

import Foundation

let temps = (0..<30).map { i in
    Temperature(value: 20.0 + 10.0 * sin(Double(i) * 0.3) + Double(i % 5) * 0.8, unit: "C")
}

let stats = Statistics(data: temps)

print("┌──────────────────────────────────────────────┐")
print("│  VPyD Swift — Protocol-Oriented Stats        │")
print("├──────────────────────────────────────────────┤")
print("│  Samples: \(temps.count)")
print("│  Mean:    \(String(format: "%.2f", stats.mean))°C")
print("│  StdDev:  \(String(format: "%.2f", stats.stddev))°C")
print("│  Range:   [\(String(format: "%.1f", stats.min)), \(String(format: "%.1f", stats.max))]°C")
print("│")
print("│  Readings:")
for (i, t) in temps.prefix(15).enumerated() {
    let bar = String(repeating: "█", count: Int(t.value / 3))
    print("│  \(String(format: "%2d", i)): \(t) \(bar)")
}
print("│  ...")
print("└──────────────────────────────────────────────┘")
''',
}


def get_demo_tabs():
    """Return the list of demo tabs for all available engines.

    Returns a list of dicts matching the addEngineTab() API:
        { engine_letter, language, code, label }
    Only engines whose toolchain is found on PATH are included,
    but the order always matches a→n.
    """
    tabs = []
    for letter in sorted(DEMO_SNIPPETS.keys()):
        if not _is_available(letter):
            continue
        snippet = DEMO_SNIPPETS[letter]
        _, lang = TOOLCHAINS[letter]
        tabs.append({
            'engine_letter': letter,
            'language': lang,
            'code': snippet['code'].strip(),
            'label': snippet['label'],
        })
    return tabs


def get_all_demo_tabs():
    """Return demo tabs for ALL engines, regardless of PATH availability.

    Includes an 'available' flag so the frontend can warn the user.
    """
    tabs = []
    for letter in sorted(DEMO_SNIPPETS.keys()):
        snippet = DEMO_SNIPPETS[letter]
        _, lang = TOOLCHAINS[letter]
        tabs.append({
            'engine_letter': letter,
            'language': lang,
            'code': snippet['code'].strip(),
            'label': snippet['label'],
            'available': _is_available(letter),
        })
    return tabs
