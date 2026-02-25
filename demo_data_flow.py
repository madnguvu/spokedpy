#!/usr/bin/env python3
"""
Demonstration of the Data Flow Visualization System.

This script shows how the data flow visualization system works with the visual editor core.
"""

import time
from visual_editor_core.models import VisualModel, VisualNode, InputPort, OutputPort, NodeType
from visual_editor_core.canvas import Canvas
from visual_editor_core.execution_engine import ExecutionEngine
from visual_editor_core.data_flow_visualizer import DataFlowVisualizer


def create_sample_model():
    """Create a sample visual model for demonstration."""
    model = VisualModel()
    
    # Create nodes
    input_node = VisualNode(
        id="input_node",
        type=NodeType.VARIABLE,
        position=(50, 100),
        outputs=[OutputPort("value", int, "Input value")]
    )
    
    transform_node = VisualNode(
        id="transform_node", 
        type=NodeType.FUNCTION,
        position=(200, 100),
        inputs=[InputPort("input", int, True, description="Value to transform")],
        outputs=[OutputPort("output", int, "Transformed value")]
    )
    
    output_node = VisualNode(
        id="output_node",
        type=NodeType.VARIABLE,
        position=(350, 100),
        inputs=[InputPort("result", int, True, description="Final result")]
    )
    
    # Add nodes to model
    model.add_node(input_node)
    model.add_node(transform_node)
    model.add_node(output_node)
    
    # Create connections
    conn1 = model.connect_nodes("input_node", "value", "transform_node", "input")
    conn2 = model.connect_nodes("transform_node", "output", "output_node", "result")
    
    return model, [conn1, conn2]


def demonstrate_data_flow_visualization():
    """Demonstrate the data flow visualization system."""
    print("🎯 Data Flow Visualization System Demo")
    print("=" * 50)
    
    # Create sample model
    print("\n1. Creating sample visual model...")
    model, connections = create_sample_model()
    print(f"   ✓ Created model with {len(model.nodes)} nodes and {len(model.connections)} connections")
    
    # Create canvas with data flow visualization
    print("\n2. Setting up canvas with data flow visualization...")
    canvas = Canvas()
    canvas.model = model
    canvas.data_flow_visualizer = DataFlowVisualizer(model)
    print("   ✓ Canvas initialized with data flow visualizer")
    
    # Set up callbacks
    def on_data_flow_update(connection_id, flow_info):
        print(f"   📊 Data flow update: {connection_id} -> {flow_info.current_value} ({flow_info.data_type})")
    
    def on_performance_alert(connection_id, level):
        print(f"   ⚠️  Performance alert: {connection_id} -> {level.value}")
    
    canvas.on_data_flow_update = on_data_flow_update
    canvas.on_performance_alert = on_performance_alert
    
    # Demonstrate data flow updates
    print("\n3. Simulating data flow through connections...")
    
    # Simulate data flowing through first connection
    print("   → Sending value 10 through first connection...")
    canvas.update_data_flow(connections[0].id, 10)
    
    # Simulate transformation
    print("   → Applying transformation (multiply by 2)...")
    canvas.highlight_data_transformation(connections[0].id, 10, 20, "multiply_by_2")
    
    # Simulate data flowing through second connection
    print("   → Sending transformed value 20 through second connection...")
    canvas.update_data_flow(connections[1].id, 20)
    
    # Update performance metrics
    print("\n4. Updating performance metrics...")
    canvas.update_connection_performance(connections[0].id, 
                                       throughput=85.0, 
                                       latency=120.0, 
                                       error_rate=1.5)
    
    canvas.update_connection_performance(connections[1].id,
                                       throughput=45.0,
                                       latency=800.0,
                                       error_rate=8.0)
    
    # Inspect connection points
    print("\n5. Inspecting connection points...")
    for i, conn in enumerate(connections):
        inspection = canvas.inspect_connection_point(conn.id, 0.5)
        print(f"   Connection {i+1} inspection:")
        print(f"     - Current value: {inspection.get('current_value')}")
        print(f"     - Data type: {inspection.get('data_type')}")
        print(f"     - Has transformation: {inspection.get('has_transformation')}")
        if 'performance' in inspection:
            perf = inspection['performance']
            print(f"     - Performance level: {perf.get('performance_level')}")
            print(f"     - Throughput: {perf.get('throughput'):.1f}")
            print(f"     - Latency: {perf.get('latency'):.1f}ms")
    
    # Check for bottlenecks
    print("\n6. Checking for performance bottlenecks...")
    bottlenecks = canvas.get_performance_bottlenecks()
    if bottlenecks:
        print(f"   ⚠️  Found {len(bottlenecks)} performance bottleneck(s):")
        for bottleneck in bottlenecks:
            print(f"     - Connection: {bottleneck['connection_id']}")
            print(f"       Error rate: {bottleneck['metrics']['error_rate']:.1f}%")
            print(f"       Latency: {bottleneck['metrics']['latency']:.1f}ms")
    else:
        print("   ✓ No critical performance bottlenecks detected")
    
    # Demonstrate tracing
    print("\n7. Demonstrating data flow tracing...")
    trace_id = canvas.start_data_flow_trace(connections[0].id, "initial_data")
    print(f"   ✓ Started trace: {trace_id}")
    
    # Simulate some data flow events
    canvas.update_data_flow(connections[0].id, 42, "calculation")
    canvas.highlight_data_transformation(connections[0].id, 42, 84, "double")
    
    # End trace and get history
    canvas.end_data_flow_trace(trace_id)
    trace_history = canvas.get_data_flow_trace_history(trace_id)
    print(f"   ✓ Trace completed with {len(trace_history)} entries")
    
    # Show visualization state
    print("\n8. Current visualization state:")
    state = canvas.data_flow_visualizer.get_visualization_state()
    print(f"   - Animation enabled: {state['animation_enabled']}")
    print(f"   - Animation speed: {state['animation_speed']}x")
    print(f"   - Connection count: {state['connection_count']}")
    print(f"   - Active particles: {state['active_particles']}")
    print(f"   - Performance bottlenecks: {state['performance_bottlenecks']}")
    
    # Demonstrate animation control
    print("\n9. Testing animation controls...")
    print("   → Setting animation speed to 2.0x...")
    canvas.set_data_flow_animation_speed(2.0)
    
    print("   → Disabling animation...")
    canvas.set_data_flow_animation(False)
    
    print("   → Re-enabling animation...")
    canvas.set_data_flow_animation(True)
    
    # Test with execution engine integration
    print("\n10. Testing execution engine integration...")
    engine = ExecutionEngine()
    engine.set_data_flow_visualizer(canvas.data_flow_visualizer)
    engine.enable_data_flow_visualization()
    
    print("    ✓ Execution engine configured with data flow visualization")
    
    # Show final state
    print("\n11. Final system state:")
    canvas_state = canvas.get_canvas_state()
    data_flow_state = canvas_state['data_flow']
    print(f"    - Total connections visualized: {data_flow_state['connection_count']}")
    print(f"    - Animation particles active: {data_flow_state['active_particles']}")
    print(f"    - Data flow enabled: {canvas_state['settings']['show_data_flow']}")
    print(f"    - Performance indicators enabled: {canvas_state['settings']['show_performance_indicators']}")
    
    print("\n✅ Data Flow Visualization Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("  • Real-time data flow visualization")
    print("  • Connection line display with direction indicators")
    print("  • Data type and value display at connection points")
    print("  • Data transformation highlighting")
    print("  • Performance bottleneck detection")
    print("  • Connection point inspection during debugging")
    print("  • Data flow tracing for complex structures")
    print("  • Animation control and particle effects")
    print("  • Integration with canvas and execution engine")


def demonstrate_advanced_features():
    """Demonstrate advanced data flow visualization features."""
    print("\n🚀 Advanced Data Flow Features Demo")
    print("=" * 50)
    
    # Create a more complex model
    model = VisualModel()
    
    # Create a processing pipeline
    nodes = []
    connections = []
    
    for i in range(4):
        node = VisualNode(
            id=f"processor_{i}",
            type=NodeType.FUNCTION,
            position=(i * 150, 100),
            inputs=[InputPort("input", int)] if i > 0 else [],
            outputs=[OutputPort("output", int)] if i < 3 else []
        )
        nodes.append(node)
        model.add_node(node)
    
    # Connect the pipeline
    for i in range(3):
        conn = model.connect_nodes(f"processor_{i}", "output", f"processor_{i+1}", "input")
        connections.append(conn)
    
    # Create visualizer
    visualizer = DataFlowVisualizer(model)
    
    print(f"\n1. Created processing pipeline with {len(nodes)} nodes")
    
    # Simulate complex data flow
    print("\n2. Simulating complex data flow patterns...")
    
    data_values = [10, 25, 60, 150]  # Increasing complexity
    transformations = ["validate", "normalize", "enhance", "finalize"]
    
    for i, (conn, value, transform) in enumerate(zip(connections, data_values, transformations)):
        print(f"   → Stage {i+1}: {transform} ({value})")
        
        # Update data flow
        visualizer.update_data_flow(conn.id, value, transform)
        
        # Simulate varying performance
        throughput = max(10, 100 - i * 20)  # Decreasing throughput
        latency = 50 + i * 100  # Increasing latency
        error_rate = i * 2  # Increasing error rate
        
        visualizer.update_performance_metrics(
            conn.id,
            throughput=throughput,
            latency=latency,
            error_rate=error_rate,
            cpu_usage=30 + i * 15
        )
    
    # Analyze performance
    print("\n3. Performance analysis:")
    bottlenecks = visualizer.get_performance_bottlenecks()
    
    for i, conn in enumerate(connections):
        metrics = visualizer.performance_metrics[conn.id]
        level = metrics.get_performance_level()
        print(f"   Stage {i+1}: {level.value.upper()}")
        print(f"     Throughput: {metrics.throughput:.1f} ops/sec")
        print(f"     Latency: {metrics.latency:.1f}ms")
        print(f"     Error rate: {metrics.error_rate:.1f}%")
    
    if bottlenecks:
        print(f"\n   ⚠️  Critical bottlenecks detected in {len(bottlenecks)} stage(s)")
    
    # Test visualization settings
    print("\n4. Testing visualization settings...")
    
    settings_tests = [
        ("Performance indicators", lambda: visualizer.set_show_performance_indicators(False)),
        ("Data labels", lambda: visualizer.set_show_data_labels(False)),
        ("Direction arrows", lambda: visualizer.set_show_direction_arrows(False)),
        ("Animation", lambda: visualizer.set_animation_enabled(False))
    ]
    
    for setting_name, setting_func in settings_tests:
        print(f"   → Disabling {setting_name.lower()}...")
        setting_func()
    
    # Re-enable everything
    print("   → Re-enabling all features...")
    visualizer.set_show_performance_indicators(True)
    visualizer.set_show_data_labels(True)
    visualizer.set_show_direction_arrows(True)
    visualizer.set_animation_enabled(True)
    
    # Test particle system
    print("\n5. Testing particle animation system...")
    
    # Get particles for first connection
    particles = visualizer.get_flow_particles(connections[0].id)
    print(f"   → Found {len(particles)} particles for first connection")
    
    if particles:
        particle = particles[0]
        print(f"     Particle position: {particle.position:.2f}")
        print(f"     Particle speed: {particle.speed:.2f}")
        print(f"     Particle color: {particle.color}")
    
    # Test cleanup
    print("\n6. Testing system cleanup...")
    initial_state = visualizer.get_visualization_state()
    print(f"   Before cleanup: {initial_state['connection_count']} connections")
    
    visualizer.cleanup()
    final_state = visualizer.get_visualization_state()
    print(f"   After cleanup: {final_state['connection_count']} connections")
    
    print("\n✅ Advanced Features Demo Complete!")


if __name__ == "__main__":
    try:
        demonstrate_data_flow_visualization()
        demonstrate_advanced_features()
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()