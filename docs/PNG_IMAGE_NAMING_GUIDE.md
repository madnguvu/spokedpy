# PNG Image Naming Guide for Visual Editor Core

## Overview

The Visual Editor Core supports custom PNG images for all node types. Images should be placed in the `web_interface/static/images/` directory and follow the naming convention below.

## Image Specifications

- **Size**: 120x80 pixels (recommended)
- **Format**: PNG with transparency support
- **Aspect Ratio**: Images will be stretched to fill the entire node area using `preserveAspectRatio="none"`
- **Text Overlay**: Node titles will be overlaid at the bottom with white stroke for readability

## Complete Naming Convention

### Core Programming Constructs
- `function_node.png` - Function
- `async_function_node.png` - Async Function  
- `lambda_node.png` - Lambda/Anonymous Function
- `method_node.png` - Method
- `property_node.png` - Property
- `class_node.png` - Class
- `variable_node.png` - Variable
- `constant_node.png` - Constant

### Control Flow
- `if_node.png` - If Condition
- `while_node.png` - While Loop
- `for_node.png` - For Loop
- `try_except_node.png` - Try/Except Block
- `break_node.png` - Break Statement
- `continue_node.png` - Continue Statement
- `return_node.png` - Return Statement
- `yield_node.png` - Yield Statement
- `raise_node.png` - Raise Exception

### Data Structures
- `list_node.png` - List
- `dict_node.png` - Dictionary
- `set_node.png` - Set
- `tuple_node.png` - Tuple
- `string_node.png` - String
- `number_node.png` - Number
- `boolean_node.png` - Boolean

### Advanced Constructs
- `decorator_node.png` - Decorator
- `generator_node.png` - Generator
- `context_manager_node.png` - Context Manager
- `comprehension_node.png` - List/Dict Comprehension
- `inheritance_node.png` - Inheritance
- `composition_node.png` - Composition
- `interface_node.png` - Interface
- `abstract_class_node.png` - Abstract Class
- `metaclass_node.png` - Metaclass

### Functional Programming
- `map_node.png` - Map Function
- `filter_node.png` - Filter Function
- `reduce_node.png` - Reduce Function
- `partial_node.png` - Partial Function
- `curry_node.png` - Curry Function

### I/O and External Operations
- `file_read_node.png` - File Read
- `file_write_node.png` - File Write
- `http_request_node.png` - HTTP Request
- `database_query_node.png` - Database Query
- `api_call_node.png` - API Call

### Timeline-Specific (Timeline Paradigm)
- `event_node.png` - Event
- `timer_node.png` - Timer
- `delay_node.png` - Delay
- `schedule_node.png` - Schedule
- `parallel_node.png` - Parallel Execution
- `sequence_node.png` - Sequential Execution
- `await_node.png` - Await

### Block-Specific (Block Paradigm)
- `statement_node.png` - Statement Block
- `expression_node.png` - Expression Block
- `block_container_node.png` - Block Container

### Diagram-Specific (Diagram Paradigm)
- `package_node.png` - Package
- `module_node.png` - Module
- `namespace_node.png` - Namespace
- `relationship_node.png` - Relationship
- `actor_node.png` - Actor (Use Case)
- `use_case_node.png` - Use Case

### Custom and Extensible
- `custom_node.png` - Custom Node
- `plugin_node.png` - Plugin Node
- `template_node.png` - Template Node

## Implementation Details

### Automatic Detection
The system automatically detects PNG images using two methods:

1. **NodeFactory Definition**: Images defined in `visual_editor_core/visual_paradigms.py`
2. **Fallback Mapping**: Hardcoded mapping in `web_interface/static/app.js`

### Fallback Behavior
If a PNG image is not found, the system falls back to:
1. Lucide SVG icons
2. Default colored rectangles with text labels

### Image Loading
- Images are loaded asynchronously
- Loading states are handled gracefully
- Broken images show a fallback icon

## Usage Examples

### Adding a New Node Image
1. Create your PNG image (120x80 pixels recommended)
2. Save it as `web_interface/static/images/your_node_type_node.png`
3. The system will automatically detect and use it

### Custom Node Types
For custom node types, add the mapping in the `getCustomNodeImage()` function in `app.js`:

```javascript
const imageMap = {
    'your_custom_type': '/static/images/your_custom_type_node.png',
    // ... other mappings
};
```

## Visual Features

### Full-Size Display
- Images fill the entire 120x80 pixel node area
- No padding or margins
- `preserveAspectRatio="none"` stretches images to fit exactly

### Text Overlay
- Node titles appear at the bottom of the image
- White stroke outline for readability against any background
- Font: 12px, weight 600, centered

### Interactive States
- **Hover**: Slight brightness increase and drop shadow
- **Selected**: Blue outline glow and enhanced brightness
- **Newly Created**: Subtle pulse animation

### Palette Display
- PNG images shown as previews in the node palette
- Bordered containers with hover effects
- Automatic scaling to fit palette item size

## Browser Compatibility

The PNG image system works in all modern browsers:
- Chrome/Chromium
- Firefox
- Safari
- Edge

High DPI displays are supported with crisp image rendering.

## Performance Considerations

- Images are cached by the browser
- Lazy loading for palette items
- Optimized SVG fallbacks for missing images
- Minimal impact on canvas performance

## Troubleshooting

### Image Not Showing
1. Check file path: `web_interface/static/images/[node_type]_node.png`
2. Verify file permissions
3. Check browser developer tools for 404 errors
4. Ensure PNG format and valid file

### Image Quality Issues
1. Use 120x80 pixel source images for best quality
2. Avoid very small source images (will be stretched)
3. Use PNG format for transparency support
4. Consider high-DPI versions for retina displays

## Future Enhancements

Planned improvements include:
- SVG image support
- Multiple image sizes for different zoom levels
- Theme-aware image variants
- User-uploadable custom images
- Image library management interface