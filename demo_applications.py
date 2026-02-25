#!/usr/bin/env python3
"""
Demo Applications for Visual Editor Core - Different Paradigms with Live Execution

This script creates comprehensive demo applications for each visual paradigm:
1. Node-Based: Data Processing Pipeline
2. Block-Based: Interactive Game Logic
3. Diagram-Based: Object-Oriented System Design
4. Timeline-Based: Async Event Processing

Each demo includes live execution with visual feedback.
"""

import sys
import time
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from visual_editor_core.models import VisualModel, VisualNode, NodeType, Connection, InputPort, OutputPort
from visual_editor_core.visual_paradigms import (
    ParadigmManager, ParadigmType, NodeBasedParadigm, BlockBasedParadigm, 
    DiagramBasedParadigm, TimelineBasedParadigm
)
from visual_editor_core.execution_engine import ExecutionEngine
from visual_editor_core.execution_visualizer import ExecutionVisualizer, ExecutionEventType


class DemoApplications:
    """Creates and runs demo applications for different visual paradigms."""
    
    def __init__(self):
        self.paradigm_manager = ParadigmManager()
        self.execution_engine = ExecutionEngine()
        self.visualizer = ExecutionVisualizer()
        
        # Set up execution visualization
        self.execution_engine.enable_debug_mode()
        self.execution_engine.enable_data_flow_visualization()
        self.visualizer.add_event_callback(self.print_execution_event)
        
        # Set up step execution callback
        self.execution_engine.set_step_execution_callback(self.on_step_execution)
    
    def print_execution_event(self, event):
        """Print execution events for console visualization."""
        timestamp = time.strftime("%H:%M:%S", time.localtime(event.timestamp))
        print(f"[{timestamp}] {event.event_type.value.upper()}: {event.message}")
        
        if event.data:
            if event.event_type == ExecutionEventType.NODE_START:
                print(f"  → Node Type: {event.data.get('node_type')}")
                if event.data.get('parameters'):
                    print(f"  → Parameters: {event.data['parameters']}")
            
            elif event.event_type == ExecutionEventType.NODE_COMPLETE:
                exec_time = event.data.get('execution_time', 0)
                print(f"  → Execution Time: {exec_time:.3f}s")
                if event.data.get('output_variables'):
                    print(f"  → Output Variables: {event.data['output_variables']}")
            
            elif event.event_type == ExecutionEventType.DATA_FLOW:
                print(f"  → Data: {event.data.get('value')} ({event.data.get('data_type')})")
                print(f"  → Flow: {event.data.get('source_node')} → {event.data.get('target_node')}")
            
            elif event.event_type == ExecutionEventType.VARIABLE_UPDATE:
                print(f"  → Variable: {event.data.get('variable_name')}")
                print(f"  → Change: {event.data.get('old_value')} → {event.data.get('new_value')}")
        
        print()  # Empty line for readability
    
    def on_step_execution(self, node_id: str, execution_state):
        """Called during step execution."""
        print(f"🔍 STEP EXECUTION - Node: {node_id}")
        print(f"   Variables: {execution_state.variables}")
        
        # Simulate step delay for visualization
        time.sleep(0.5)
    
    def create_node_based_demo(self) -> VisualModel:
        """Create a node-based data processing pipeline demo."""
        print("🔧 Creating Node-Based Demo: Data Processing Pipeline")
        print("=" * 60)
        
        model = VisualModel()
        
        # Create nodes for data processing pipeline
        # 1. Data Input Node
        input_node = VisualNode(
            id="data_input",
            type=NodeType.VARIABLE,
            position=(100, 100),
            parameters={'variable_name': 'raw_data', 'initial_value': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]},
            metadata={'name': 'Raw Data Input', 'description': 'Input dataset'}
        )
        input_node.outputs.append(OutputPort(name='data', data_type=list))
        model.add_node(input_node)
        
        # 2. Filter Node (remove even numbers)
        filter_node = VisualNode(
            id="filter_data",
            type=NodeType.FUNCTION,
            position=(300, 100),
            parameters={'function_name': 'filter_odds', 'expression': 'lambda x: x % 2 == 1'},
            metadata={'name': 'Filter Odds', 'description': 'Filter odd numbers only'}
        )
        filter_node.inputs.append(InputPort(name='input_data', data_type=list))
        filter_node.outputs.append(OutputPort(name='filtered_data', data_type=list))
        model.add_node(filter_node)
        
        # 3. Transform Node (square the numbers)
        transform_node = VisualNode(
            id="transform_data",
            type=NodeType.FUNCTION,
            position=(500, 100),
            parameters={'function_name': 'square_numbers', 'expression': 'lambda x: x ** 2'},
            metadata={'name': 'Square Transform', 'description': 'Square each number'}
        )
        transform_node.inputs.append(InputPort(name='input_data', data_type=list))
        transform_node.outputs.append(OutputPort(name='transformed_data', data_type=list))
        model.add_node(transform_node)
        
        # 4. Aggregate Node (sum all values)
        aggregate_node = VisualNode(
            id="aggregate_data",
            type=NodeType.FUNCTION,
            position=(700, 100),
            parameters={'function_name': 'sum_values', 'expression': 'sum'},
            metadata={'name': 'Sum Aggregation', 'description': 'Sum all values'}
        )
        aggregate_node.inputs.append(InputPort(name='input_data', data_type=list))
        aggregate_node.outputs.append(OutputPort(name='result', data_type=int))
        model.add_node(aggregate_node)
        
        # 5. Output Node
        output_node = VisualNode(
            id="output_result",
            type=NodeType.VARIABLE,
            position=(900, 100),
            parameters={'variable_name': 'final_result'},
            metadata={'name': 'Final Result', 'description': 'Pipeline output'}
        )
        output_node.inputs.append(InputPort(name='value', data_type=int))
        model.add_node(output_node)
        
        # Create connections
        connections = [
            Connection(id="conn1", source_node_id="data_input", source_port="data", 
                      target_node_id="filter_data", target_port="input_data"),
            Connection(id="conn2", source_node_id="filter_data", source_port="filtered_data",
                      target_node_id="transform_data", target_port="input_data"),
            Connection(id="conn3", source_node_id="transform_data", source_port="transformed_data",
                      target_node_id="aggregate_data", target_port="input_data"),
            Connection(id="conn4", source_node_id="aggregate_data", source_port="result",
                      target_node_id="output_result", target_port="value")
        ]
        
        for conn in connections:
            model.add_connection(conn)
        
        print(f"✅ Created node-based model with {len(model.nodes)} nodes and {len(model.connections)} connections")
        return model
    
    def create_block_based_demo(self) -> VisualModel:
        """Create a block-based interactive game logic demo."""
        print("🎮 Creating Block-Based Demo: Interactive Game Logic")
        print("=" * 60)
        
        model = VisualModel()
        
        # Game state variables
        score_node = VisualNode(
            id="game_score",
            type=NodeType.VARIABLE,
            position=(100, 100),
            parameters={'variable_name': 'score', 'initial_value': 0},
            metadata={'name': 'Game Score', 'description': 'Player score', 'block_type': 'variable_set'}
        )
        model.add_node(score_node)
        
        lives_node = VisualNode(
            id="player_lives",
            type=NodeType.VARIABLE,
            position=(100, 200),
            parameters={'variable_name': 'lives', 'initial_value': 3},
            metadata={'name': 'Player Lives', 'description': 'Remaining lives', 'block_type': 'variable_set'}
        )
        model.add_node(lives_node)
        
        # Game loop condition
        game_active_node = VisualNode(
            id="game_active",
            type=NodeType.CONTROL_FLOW,
            position=(300, 150),
            parameters={'condition': 'lives > 0'},
            metadata={'name': 'Game Active?', 'description': 'Check if game should continue', 'block_type': 'if_statement'}
        )
        game_active_node.inputs.append(InputPort(name='lives', data_type=int))
        game_active_node.outputs.append(OutputPort(name='continue', data_type=bool))
        game_active_node.outputs.append(OutputPort(name='game_over', data_type=bool))
        model.add_node(game_active_node)
        
        # Player action simulation
        action_node = VisualNode(
            id="player_action",
            type=NodeType.FUNCTION,
            position=(500, 100),
            parameters={'function_name': 'simulate_action', 'success_rate': 0.7},
            metadata={'name': 'Player Action', 'description': 'Simulate player action', 'block_type': 'function_call'}
        )
        action_node.outputs.append(OutputPort(name='success', data_type=bool))
        action_node.outputs.append(OutputPort(name='points', data_type=int))
        model.add_node(action_node)
        
        # Score update
        score_update_node = VisualNode(
            id="update_score",
            type=NodeType.FUNCTION,
            position=(700, 50),
            parameters={'function_name': 'add_points'},
            metadata={'name': 'Update Score', 'description': 'Add points to score', 'block_type': 'variable_set'}
        )
        score_update_node.inputs.append(InputPort(name='current_score', data_type=int))
        score_update_node.inputs.append(InputPort(name='points', data_type=int))
        score_update_node.outputs.append(OutputPort(name='new_score', data_type=int))
        model.add_node(score_update_node)
        
        # Lives update (on failure)
        lives_update_node = VisualNode(
            id="update_lives",
            type=NodeType.FUNCTION,
            position=(700, 200),
            parameters={'function_name': 'lose_life'},
            metadata={'name': 'Lose Life', 'description': 'Decrease lives on failure', 'block_type': 'variable_set'}
        )
        lives_update_node.inputs.append(InputPort(name='current_lives', data_type=int))
        lives_update_node.outputs.append(OutputPort(name='new_lives', data_type=int))
        model.add_node(lives_update_node)
        
        # Create connections for game flow
        connections = [
            Connection(id="conn1", source_node_id="player_lives", source_port="value",
                      target_node_id="game_active", target_port="lives"),
            Connection(id="conn2", source_node_id="game_active", source_port="continue",
                      target_node_id="player_action", target_port="trigger"),
            Connection(id="conn3", source_node_id="player_action", source_port="points",
                      target_node_id="update_score", target_port="points"),
            Connection(id="conn4", source_node_id="game_score", source_port="value",
                      target_node_id="update_score", target_port="current_score"),
            Connection(id="conn5", source_node_id="player_lives", source_port="value",
                      target_node_id="update_lives", target_port="current_lives")
        ]
        
        for conn in connections:
            model.add_connection(conn)
        
        print(f"✅ Created block-based model with {len(model.nodes)} nodes and {len(model.connections)} connections")
        return model
    
    def create_diagram_based_demo(self) -> VisualModel:
        """Create a diagram-based object-oriented system design demo."""
        print("📊 Creating Diagram-Based Demo: Object-Oriented System Design")
        print("=" * 60)
        
        model = VisualModel()
        
        # Base class
        animal_class = VisualNode(
            id="animal_class",
            type=NodeType.CLASS,
            position=(300, 100),
            parameters={'class_name': 'Animal', 'is_abstract': True},
            metadata={'name': 'Animal', 'description': 'Base animal class', 'diagram_type': 'abstract_class'}
        )
        model.add_node(animal_class)
        
        # Derived classes
        dog_class = VisualNode(
            id="dog_class",
            type=NodeType.CLASS,
            position=(150, 250),
            parameters={'class_name': 'Dog', 'parent_class': 'Animal'},
            metadata={'name': 'Dog', 'description': 'Dog implementation', 'diagram_type': 'class'}
        )
        model.add_node(dog_class)
        
        cat_class = VisualNode(
            id="cat_class",
            type=NodeType.CLASS,
            position=(450, 250),
            parameters={'class_name': 'Cat', 'parent_class': 'Animal'},
            metadata={'name': 'Cat', 'description': 'Cat implementation', 'diagram_type': 'class'}
        )
        model.add_node(cat_class)
        
        # Interface
        pet_interface = VisualNode(
            id="pet_interface",
            type=NodeType.CLASS,
            position=(600, 100),
            parameters={'interface_name': 'IPet', 'is_interface': True},
            metadata={'name': 'IPet', 'description': 'Pet interface', 'diagram_type': 'interface'}
        )
        model.add_node(pet_interface)
        
        # Composition - Pet Owner
        owner_class = VisualNode(
            id="owner_class",
            type=NodeType.CLASS,
            position=(300, 400),
            parameters={'class_name': 'PetOwner'},
            metadata={'name': 'PetOwner', 'description': 'Pet owner class', 'diagram_type': 'class'}
        )
        model.add_node(owner_class)
        
        # Create relationships
        connections = [
            # Inheritance relationships
            Connection(id="inherit1", source_node_id="dog_class", source_port="inherits",
                      target_node_id="animal_class", target_port="base"),
            Connection(id="inherit2", source_node_id="cat_class", source_port="inherits",
                      target_node_id="animal_class", target_port="base"),
            
            # Interface implementation
            Connection(id="impl1", source_node_id="dog_class", source_port="implements",
                      target_node_id="pet_interface", target_port="interface"),
            Connection(id="impl2", source_node_id="cat_class", source_port="implements",
                      target_node_id="pet_interface", target_port="interface"),
            
            # Composition relationship
            Connection(id="comp1", source_node_id="owner_class", source_port="has",
                      target_node_id="pet_interface", target_port="component")
        ]
        
        for conn in connections:
            model.add_connection(conn)
        
        print(f"✅ Created diagram-based model with {len(model.nodes)} nodes and {len(model.connections)} connections")
        return model
    
    def create_timeline_based_demo(self) -> VisualModel:
        """Create a timeline-based async event processing demo."""
        print("⏰ Creating Timeline-Based Demo: Async Event Processing")
        print("=" * 60)
        
        model = VisualModel()
        
        # Event trigger
        event_trigger = VisualNode(
            id="event_trigger",
            type=NodeType.FUNCTION,
            position=(100, 200),
            parameters={'event_name': 'user_click', 'interval': 1.0},
            metadata={'name': 'User Click Event', 'description': 'Simulates user clicks', 'temporal_type': 'event'}
        )
        event_trigger.outputs.append(OutputPort(name='event', data_type=dict))
        model.add_node(event_trigger)
        
        # Parallel processing branches
        validation_process = VisualNode(
            id="validation_process",
            type=NodeType.ASYNC,
            position=(300, 100),
            parameters={'function_name': 'validate_input', 'duration': 0.5},
            metadata={'name': 'Input Validation', 'description': 'Async input validation', 'temporal_type': 'process'}
        )
        validation_process.inputs.append(InputPort(name='event_data', data_type=dict))
        validation_process.outputs.append(OutputPort(name='valid', data_type=bool))
        model.add_node(validation_process)
        
        logging_process = VisualNode(
            id="logging_process",
            type=NodeType.ASYNC,
            position=(300, 300),
            parameters={'function_name': 'log_event', 'duration': 0.2},
            metadata={'name': 'Event Logging', 'description': 'Async event logging', 'temporal_type': 'process'}
        )
        logging_process.inputs.append(InputPort(name='event_data', data_type=dict))
        logging_process.outputs.append(OutputPort(name='logged', data_type=bool))
        model.add_node(logging_process)
        
        # Synchronization point
        sync_point = VisualNode(
            id="sync_point",
            type=NodeType.ASYNC,
            position=(500, 200),
            parameters={'function_name': 'await_all', 'timeout': 2.0},
            metadata={'name': 'Sync Point', 'description': 'Wait for all processes', 'temporal_type': 'sync_point'}
        )
        sync_point.inputs.append(InputPort(name='validation_result', data_type=bool))
        sync_point.inputs.append(InputPort(name='logging_result', data_type=bool))
        sync_point.outputs.append(OutputPort(name='all_complete', data_type=bool))
        model.add_node(sync_point)
        
        # Response generation
        response_gen = VisualNode(
            id="response_gen",
            type=NodeType.FUNCTION,
            position=(700, 200),
            parameters={'function_name': 'generate_response'},
            metadata={'name': 'Generate Response', 'description': 'Create user response', 'temporal_type': 'process'}
        )
        response_gen.inputs.append(InputPort(name='processing_complete', data_type=bool))
        response_gen.outputs.append(OutputPort(name='response', data_type=str))
        model.add_node(response_gen)
        
        # Timer for timeout handling
        timeout_timer = VisualNode(
            id="timeout_timer",
            type=NodeType.TIMER,
            position=(500, 350),
            parameters={'duration': 3.0, 'action': 'timeout_handler'},
            metadata={'name': 'Timeout Timer', 'description': 'Handle processing timeout', 'temporal_type': 'timer'}
        )
        timeout_timer.outputs.append(OutputPort(name='timeout', data_type=bool))
        model.add_node(timeout_timer)
        
        # Create temporal connections
        connections = [
            # Event to parallel processes
            Connection(id="conn1", source_node_id="event_trigger", source_port="event",
                      target_node_id="validation_process", target_port="event_data"),
            Connection(id="conn2", source_node_id="event_trigger", source_port="event",
                      target_node_id="logging_process", target_port="event_data"),
            
            # Parallel processes to sync point
            Connection(id="conn3", source_node_id="validation_process", source_port="valid",
                      target_node_id="sync_point", target_port="validation_result"),
            Connection(id="conn4", source_node_id="logging_process", source_port="logged",
                      target_node_id="sync_point", target_port="logging_result"),
            
            # Sync point to response
            Connection(id="conn5", source_node_id="sync_point", source_port="all_complete",
                      target_node_id="response_gen", target_port="processing_complete"),
            
            # Timeout handling
            Connection(id="conn6", source_node_id="timeout_timer", source_port="timeout",
                      target_node_id="response_gen", target_port="timeout_signal")
        ]
        
        for conn in connections:
            model.add_connection(conn)
        
        print(f"✅ Created timeline-based model with {len(model.nodes)} nodes and {len(model.connections)} connections")
        return model
    
    def execute_demo_with_visualization(self, model: VisualModel, demo_name: str):
        """Execute a demo model with full visualization."""
        print(f"\n🚀 EXECUTING {demo_name.upper()}")
        print("=" * 60)
        
        # Clear previous events
        self.visualizer.clear_events()
        
        # Set visualization parameters
        self.visualizer.set_execution_speed(1.0)
        self.visualizer.set_highlight_duration(1.5)
        self.visualizer.enable_animation()
        
        # Start execution
        start_time = time.time()
        
        try:
            # Execute with step-by-step visualization
            result = self.execution_engine.execute_model(model)
            
            execution_time = time.time() - start_time
            
            # Signal completion
            self.visualizer.complete_execution(
                success=result.success,
                final_variables=result.variables,
                execution_time=execution_time
            )
            
            # Print results
            print(f"\n📊 EXECUTION RESULTS")
            print("-" * 30)
            print(f"Success: {result.success}")
            print(f"Execution Time: {execution_time:.3f}s")
            
            if result.success:
                print(f"Output: {result.output}")
                if result.variables:
                    print("Final Variables:")
                    for name, value in result.variables.items():
                        if not name.startswith('__'):
                            print(f"  {name}: {value}")
            else:
                print(f"Error: {result.error}")
                if result.traceback:
                    print(f"Traceback: {result.traceback}")
            
            # Print execution summary
            summary = self.visualizer.get_execution_summary()
            print(f"\n📈 EXECUTION SUMMARY")
            print("-" * 30)
            print(f"Total Events: {summary['total_events']}")
            print(f"Nodes Executed: {summary['nodes_executed']}")
            print(f"Event Breakdown:")
            for event_type, count in summary['event_counts'].items():
                print(f"  {event_type}: {count}")
            
        except Exception as e:
            self.visualizer.error_execution(e)
            print(f"❌ Execution failed: {e}")
    
    def run_all_demos(self):
        """Run all paradigm demos with visualization."""
        print("🎯 VISUAL EDITOR CORE - PARADIGM DEMOS")
        print("=" * 60)
        print("This demo showcases live execution with visual feedback")
        print("across all supported visual programming paradigms.")
        print()
        
        demos = [
            ("Node-Based: Data Processing Pipeline", self.create_node_based_demo),
            ("Block-Based: Interactive Game Logic", self.create_block_based_demo),
            ("Diagram-Based: Object-Oriented Design", self.create_diagram_based_demo),
            ("Timeline-Based: Async Event Processing", self.create_timeline_based_demo)
        ]
        
        for demo_name, create_func in demos:
            try:
                # Create the demo model
                model = create_func()
                
                # Execute with visualization
                self.execute_demo_with_visualization(model, demo_name)
                
                print(f"\n✅ {demo_name} completed successfully!")
                print("Press Enter to continue to next demo...")
                input()
                
            except Exception as e:
                print(f"❌ Error in {demo_name}: {e}")
                import traceback
                traceback.print_exc()
            
            print("\n" + "="*80 + "\n")
        
        print("🎉 All paradigm demos completed!")
        print("Check the web interface at http://localhost:5002 to see the visual models.")


def main():
    """Main function to run the demos."""
    print("Starting Visual Editor Core Demo Applications...")
    
    # Create and run demos
    demo_app = DemoApplications()
    demo_app.run_all_demos()


if __name__ == "__main__":
    main()