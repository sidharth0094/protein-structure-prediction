import torch
import torchvision
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from utils.helper import  Extract
import math


class RNN(nn.Module):
  def __init__(self, hidden_size=20):
    super(RNN, self).__init__()
    
    self.input_size = 20
    self.hidden_size = hidden_size
    self.output_size= 1
    
    self.linear1 = torch.nn.Linear(self.input_size+hidden_size, self.hidden_size)
    self.linear2 = torch.nn.Linear(self.hidden_size, self.output_size)

  def forward(self, x, last_hidden):
    combined = torch.cat((x, last_hidden), 1)
    out_1 = self.linear1(combined)
    h1_relu = torch.clamp(out_1,0,1)
    #h1_relu = F.tanh(out_1)
    out_2 = self.linear2(h1_relu)
    y_pred = F.relu(out_2)
    return y_pred, h1_relu

  def initHidden(self):
    return torch.zeros(1, self.hidden_size)
  def randHidden(self):
    return torch.rand(1, self.hidden_size)
    
    
class TrainRNN:
  def __init__(self, hidden_size=20, decay_rate = 0):
    self.extractor = Extract()
    self.model = RNN(hidden_size)
    self.criterion = torch.nn.MSELoss(reduction='sum')
    self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3, weight_decay = decay_rate)
    self.traindfXY = None
    self.testdfXY = None
    self.xd = None
    self.yd = None
    self.hidden_size = hidden_size


  def loadTestTrainData(self, one_hot_encoded_df_train_list, one_hot_encoded_df_test_list, logging=False, max_size = 40000):
    if logging:
        print('Train data extraction started.') 
    self.traindfXY = self.extractor.get_whole_seq_data(one_hot_encoded_df_train_list, logging, max_size)
    self.xd, self.yd = len(self.traindfXY), len(self.traindfXY)
	
    #print(self.xd)

    if logging:
        print('Test data extraction started.') 
    self.testdfXY = self.extractor.get_whole_seq_data(one_hot_encoded_df_test_list, logging, max_size)
    
    if logging:
        print("Test and Train data extracted.")

  def trainNN(self, num_epochs=5, logging=False, save_path=None, save_after_epochs=None, recur = 1, random = False):
    batch_size = 1
    for epoch in range(num_epochs):
      # shuffle dataset
      np.random.shuffle(self.traindfXY)
      num_prots = len(self.traindfXY)
      total_epoch_loss = 0
      for i in range(num_prots):
        #Get a protein
        if logging and (i % 100 == 0) and (i > 0):
          print(i)
        trainX, trainY = self.traindfXY[i]
        num_acids, _ = trainX.shape
        #print(num_acids, type(trainX))
        # _ = input("t")
        for r in range(recur):
          self.optimizer.zero_grad()
          if random:
            hidden = self.model.randHidden()
          else:
            hidden = self.model.initHidden()
          y_pred_tensor = torch.zeros(batch_size, num_acids)
          for j in range(num_acids):
            tensorX = torch.tensor(trainX[j], dtype=torch.float).view(batch_size, 20)
            # Run Model One Acid
            y_pred, hidden = self.model(tensorX, hidden)
            y_pred_tensor[0][j] = y_pred
          y_true_tensor = torch.tensor(trainY, dtype=torch.float).view(batch_size, num_acids)
          loss = torch.sqrt(self.criterion(y_pred_tensor, y_true_tensor))
          #perform backward pass, update weights
          loss.backward() 
          self.optimizer.step()
        total_epoch_loss += loss.item()
      avg_epoch_loss = total_epoch_loss / num_prots

      if save_after_epochs != None and epoch%save_after_epochs == 0:
        torch.save(self.model.state_dict(), save_path)

      if logging:
        print("Epoch: {} Current Loss: {} Avg Loss: {}".format(epoch + 1, loss.item(), avg_epoch_loss))


  def predict(self, inputdfXY, batch_size = 1, start = 0, single_protein = False):
    num_prots = len(inputdfXY)
    protein_list = []
    for i in range(start, num_prots):
      #Get a protein
      testX, testY = inputdfXY[i]
      num_acids, _ = testX.shape
      hidden = self.model.initHidden()
      y_pred_tensor = torch.zeros(batch_size, num_acids)
      for j in range(num_acids):
        tensorX = torch.tensor(testX[j], dtype=torch.float).view(batch_size, 20)
        # Run Model One Acid
        y_pred, hidden = self.model(tensorX, hidden)
        y_pred_tensor[0][j] = y_pred.item()
      y_true_tensor = torch.tensor(testY, dtype=torch.float).view(batch_size, num_acids)
      loss = torch.sqrt(self.criterion(y_pred_tensor, y_true_tensor))
      avg_loss = loss.item() / num_acids 
      protein_list.append((avg_loss,y_pred_tensor.detach().numpy(),y_true_tensor.detach().numpy()))
      if single_protein:
        break
    return protein_list
  
  
  def predict_on_test_data(self, batch_size = 1, start = 0, single_protein = False):
    return self.predict(self.testdfXY, batch_size, start, single_protein)

  def predict_on_outside_data(self, outside_data_one_hot_df_list, batch_size = 1, start = 0, single_protein = False, logging = False, max_size = 40000):
    if logging:
      print("Seperating Labels")
    outsideXY = self.extractor.get_whole_seq_data(outside_data_one_hot_df_list, logging, max_size)
    if logging:
      print("Running Predictions")
    return self.predict(outsideXY, batch_size, start, single_protein)