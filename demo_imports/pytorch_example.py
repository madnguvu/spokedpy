import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
# Load the dataset
file_path = r'c:\tmp\data.csv'
data = pd.read_csv(file_path, delimiter='\t')

# Extract the columns and convert to binary representation
columns = [f'num{i}' for i in range(1, 21)]
data_binary = pd.get_dummies(data[columns].stack()).groupby(level=0).sum()

# Prepare the dataset
data_tensor = torch.tensor(data_binary.values, dtype=torch.float32)
labels = data[columns].values

# Split into training, validation, and test sets
train_data = data_tensor[:-50]
train_labels = labels[:-50]
val_data = data_tensor[-50:-10]
val_labels = labels[-50:-10]
test_data = data_tensor[-10:]
test_labels = labels[-10:]

# Define the model
class Predictor(nn.Module):
    def __init__(self, input_size, output_size):
        super(Predictor, self).__init__()
        self.fc = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLU(),
            nn.Linear(128, 256),
            nn.ReLU(),
            nn.Linear(256, output_size)
        )
    
    def forward(self, x):
        return self.fc(x)

# Initialize the model, loss function, and optimizer
input_size = data_tensor.shape[1]
output_size = 20  # Predict 20 numbers
model = Predictor(input_size, output_size)
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# Train the model
epochs = 100
for epoch in range(epochs):
    model.train()
    optimizer.zero_grad()
    outputs = model(train_data)
    loss = criterion(outputs, torch.tensor(train_labels, dtype=torch.long))
    loss.backward()
    optimizer.step()

# Validate the model
model.eval()
with torch.no_grad():
    val_outputs = model(val_data)
    val_loss = criterion(val_outputs, torch.tensor(val_labels, dtype=torch.long))
    print(f'Validation Loss: {val_loss.item()}')

# Predict the next 40 drawings
predictions = []
with torch.no_grad():
    for i in range(40):
        test_output = model(test_data)
        prediction = torch.argmax(test_output, dim=1).numpy()
        predictions.append(prediction)
        # Update test_data with the new prediction
        new_row = np.zeros((1, input_size))
        for num in prediction:
            new_row[0, num] = 1
        test_data = torch.cat((test_data[1:], torch.tensor(new_row, dtype=torch.float32)))

# Save predictions to a file
output_file = r'c:\tmp\predictions.txt'
with open(output_file, 'w') as f:
    for pred in predictions:
        f.write(' '.join(map(str, pred)) + '\n')

print(f'Predictions saved to {output_file}')