from taalkit import *
from random import random, choice, sample, randrange
import hugo_functions as hufu
import logistic_growth_functions as lgf
import pandas as pd
import time
import statistics as stat

import matplotlib.pyplot as plt


class Parameters:


    def read(self, parmfile):
        '''Read a set of parameters from a disk file.'''
        parms_stuff = pd.read_csv(parmfile, delimiter = " = ", header=None, index_col=0)
        parms = parms_stuff.T   #transpose data frame

        self.N_RUNS = int(parms["N_RUNS"].get_value(1))

        self.NUM_LOCATIONS = int(parms["NUM_LOCATIONS"].get_value(1))

        self.POP_1_SIZES = [int(x) for x in parms["POP_1_SIZE"].get_value(1).strip('()').split(',')]  # e.g. [167, 167, 166, 0, 0]
        self.POP_2_SIZES = [int(x) for x in parms["POP_2_SIZE"].get_value(1).strip('()').split(',')]

        self.POP_1_SIZE = sum(self.POP_1_SIZES)
        self.POP_2_SIZE = sum(self.POP_2_SIZES)

        self.INITIAL_UTTERANCES = int(parms["INITIAL_UTTERANCES"].get_value(1))
        self.CROSS_INTERACTION = float(parms["CROSS_INTERACTION"].get_value(1))
        self.NR_OF_INTERACTIONS = int(parms["NR_OF_INTERACTIONS"].get_value(1))

        self.PRINT_EVERY_N = int(parms["PRINT_EVERY_N"].get_value(1))

        self.DO_REMOVE_EXEMPLARS = int(parms["DO_REMOVE_EXEMPLARS"].get_value(1))

        self.DOUBT_STEP = float(parms["DOUBT_STEP"].get_value(1))
        self.DOUBT_INFLUENCE = float(parms["DOUBT_INFLUENCE"].get_value(1))

        self.USE_SIGMOID = int(parms["USE_SIGMOID"].get_value(1))

        self.G_VF = float(parms["G_VF"].get_value(1))
        self.G_THEN = float(parms["G_THEN"].get_value(1))

        self.USE_DEATH = int(parms["USE_DEATH"].get_value(1))
        self.DIE_AFTER_N = int(parms["DIE_AFTER_N"].get_value(1))

class Agent:
  '''Represents a participant in language change experiments.'''

  def __init__(self, parms):
    self.generate_exemplars(parms)          # creates an inventory of exemplars to the rato of the initial frequencies
    self.get_doubt(parms) # determines an position on the x axis of the sigmoid.

    self.g_Vf = parms.G_VF
    self.g_THEN = parms.G_THEN
    self.count_speak = 0
    self.count_hear = 0

  def generate_exemplars(self, parms):
    '''Build the agent’s initial language model based on historical frequencies.'''
    self.utterances = FrequencyTable()  # The agent’s language model
    for i in range(parms.INITIAL_UTTERANCES):
      utterance = self.hist_freq.random_utterance()
      self.utterances.add_utterance(utterance)

  def get_doubt(self, parms):
    ''' Computes the average probability of an Agent producing V2.
    With this probability it determines how much "doubt" this agent has.
    This is done with the sigmoid function but with the y value as input instead of the x value'''
    V2_P = []
    V2_P.append(self.utterances.Vf.V2_fraction())
    V2_P.append(self.utterances.Aux.V2_fraction())
    V2_P.append(self.utterances.THEN.V2_fraction())
    V2_P.append(self.utterances.AdvO.V2_fraction())

    av_P_V2 = stat.mean(V2_P)

    # Prevent division by zero
    if av_P_V2 < 0.001: av_P_V2 = 0.001

    self.doubt = lgf.inverse_sigmoid(av_P_V2, 1, .1)


  def speak(self, interaction_number, parms):
    '''Produces a random utterance based on the agent’s language model.'''

    self.count_speak += 1

    if self.utterances.Total == 0:
      print("RAN OUT OF EXEMPLARS!")
      exit()
    exemplar = self.utterances.random_exemplar()

    P_Vf_V2 = self.utterances.Vf.V2_fraction()
    P_Aux_V2 = self.utterances.Aux.V2_fraction()
    P_THEN_V2 = self.utterances.THEN.V2_fraction()
    P_AdvO_V2 = self.utterances.AdvO.V2_fraction()

    P_verb_V2 = P_Vf_V2 if exemplar.verb == 'Vf' else P_Aux_V2
    P_adverb_V2 = P_THEN_V2 if exemplar.adverb == 'THEN' else P_AdvO_V2

    # TODO: welke formule?
    # P_V2 = P_verb_V2 + P_adverb_V2  # paper -- can be > 1 ?!?
    # P_V2 = (P_verb_V2 + P_adverb_V2) / 2  # average
    # P_V2 = P_verb_V2 + P_adverb_V2 - P_verb_V2 * P_adverb_V2  # independent

    # P_V2 = lgf.sigmoid(self.doubt, 1, .1)

    if parms.USE_SIGMOID == 1: #use sigmoid as wel as ' classical probability'
        ''' Compute a weighed average of the doubt and the other Probabilities of V2 '''
        P_V2 = (P_verb_V2 + P_adverb_V2 + parms.DOUBT_INFLUENCE * lgf.sigmoid(self.doubt, 1, .1)) / (parms.DOUBT_INFLUENCE + 2)  # average
    elif parms.USE_SIGMOID == 2: #use sigmoid probability only
        P_V2 = lgf.sigmoid(self.doubt, 1, .1)
    else:  #do not use sigmoid probability
        P_V2 = (P_verb_V2 + P_adverb_V2) / 2  # average
        #P_V2 = P_verb_V2 + P_adverb_V2  # paper -- can be > 1 ?!?
        #P_V2 = P_verb_V2 + P_adverb_V2 - P_verb_V2 * P_adverb_V2  # independent

    V2 = random() < P_V2
    utterance = Utterance(exemplar, V2)

    if utterance.V2:
        self.doubt += parms.DOUBT_STEP
    else:
        self.doubt -= parms.DOUBT_STEP

    # Growth
    if parms.DO_REMOVE_EXEMPLARS and not (self.alert(interaction_number,parms)):
      self.utterances.remove_utterance(utterance)

    return utterance

  def hear(self, utterance, parms):
    '''Consumes an utterance by updating the agent’s language model.'''

    self.count_hear += 1

    self.utterances.add_utterance(utterance)

    if utterance.V2:
        self.doubt += parms.DOUBT_STEP
    else:
        self.doubt -= parms.DOUBT_STEP



class Celt(Agent):

    def __init__(self, parms, location):
        super().__init__(parms)
        self.location = location

    POP_TYPE = 1

    def alert(self, i, parms):
      '''Determines when to apply the growth factors'''
      if self.g_Vf > 0 and i % (parms.POP_1_SIZE // self.g_Vf) == 0 and self.utterances.Vf.Total < self.utterances.Aux.Total:
        return True
      if self.g_THEN > 0 and i % (parms.POP_1_SIZE // self.g_THEN) == 0 and self.utterances.THEN.Total < self.utterances.AdvO.Total:
        return True
      return False


class Viking(Agent):

    def __init__(self, parms, location):
        super().__init__(parms)
        self.location = location

    POP_TYPE = 2

    def alert(self, i, parms):
      '''Determines when to apply the growth factors'''
      if self.g_Vf > 0 and i % (parms.POP_2_SIZE // self.g_Vf) == 0 and self.utterances.Vf.Total < self.utterances.Aux.Total:
        return True
      if self.g_THEN > 0 and i % (parms.POP_2_SIZE // self.g_THEN) == 0 and self.utterances.THEN.Total < self.utterances.AdvO.Total:
        return True
      return False


def main():

  # Create two populations
  pop1_file = 'celt_M3.txt'

  pop2_file = 'viking_M3.txt'

  figname = 'figure.png'
  parmfile = "parmfile.txt"
  #TODO: Fix parms

  pop1_file, pop2_file, figname, parmfile = hufu.read_cmd_line(pop1_file, pop2_file, figname, parmfile)

  print ("Read parameters")

  parms = Parameters()
  parms.read(parmfile)

  print ("Start Experiment of {} Runs".format(parms.N_RUNS))
  for i in range (0, parms.N_RUNS):

      print ('\n--- Run {} of {} ---\n'.format(i + 1, parms.N_RUNS))

      pop1_bookkeep = []
      for loc in range(parms.NUM_LOCATIONS):
          pop1_bookkeep.append([])
      x_1 = []
      for loc in range(parms.NUM_LOCATIONS):
          x_1.append([])
      pop2_bookkeep = []
      for loc in range(parms.NUM_LOCATIONS):
          pop2_bookkeep.append([])
      x_2 = []
      for loc in range(parms.NUM_LOCATIONS):
          x_2.append([])

      Celt.hist_freq = read_frequencies(pop1_file)
      Viking.hist_freq = read_frequencies(pop2_file)
      print('Fraction of V2 sentences')
      print('    #  ', end='')
      for location in range(parms.NUM_LOCATIONS):
        print('    Celt  Viking', end='')
      print()
      print('-------', end='')
      for location in range(parms.NUM_LOCATIONS):
        print('   ------ ------', end='')
      print()
      print('   0.0%', end='')
      for location in range(parms.NUM_LOCATIONS):
        if parms.POP_1_SIZES[location] > 0:
          print('   {:.4f}'.format(Celt.hist_freq.Total.V2_fraction()), end='')
        else:
          print('     --  ', end='')
        if parms.POP_2_SIZES[location] > 0:
          print(' {:.4f}'.format(Viking.hist_freq.Total.V2_fraction()), end='')
        else:
          print('   --  ', end='')
      print()

      population_1 = []
      for location, size in enumerate(parms.POP_1_SIZES):
          for i in range(size):
              population_1.append(Celt(parms, location))
      population_2 = []
      for location, size in enumerate(parms.POP_2_SIZES):
          for i in range(size):
              population_2.append(Viking(parms, location))
      population = population_1 + population_2

      # Global statistics of all utterances (for plotting purposes).
      # @Hugo: use this instead of Agent.count_speak etc.
      pop1_utterances = []
      for loc in range(parms.NUM_LOCATIONS):
          pop1_utterances.append(FrequencyTable())
      pop2_utterances = []
      for loc in range(parms.NUM_LOCATIONS):
          pop2_utterances.append(FrequencyTable())

      # Interact the populations
      for interaction_number in range(1, parms.NR_OF_INTERACTIONS + 1):

        # Select a speaker and a listener
        while True:
            if random() >= parms.CROSS_INTERACTION:
                if random() < parms.POP_1_SIZE/(parms.POP_1_SIZE +  parms.POP_2_SIZE):
                    speaker, listener = sample(population_1, 2)
                else:
                    speaker, listener = sample(population_2, 2)
            else:
                if random() < parms.POP_1_SIZE/(parms.POP_1_SIZE +  parms.POP_2_SIZE):
                    speaker, x = sample(population_1,2)  # speaker = choice(population_1)
                    listener, x = sample(population_2,2)
                else:
                    speaker, x = sample(population_2, 2)
                    listener, x = sample(population_1, 2)
            if abs(speaker.location - listener.location) <= 1: break

        # Interact!
        utterance = speaker.speak(interaction_number, parms)
        listener.hear(utterance, parms)

        if isinstance(speaker, Celt):
          pop1_utterances[speaker.location].add_utterance(utterance)
          pop1_bookkeep[speaker.location].append(pop1_utterances[speaker.location].Total.V2_fraction()) # do bookkeeping for the sake of plotting
          x_1[speaker.location].append(interaction_number) # generate values for x axis. This is necesarry to have both bookkeeping arrays nicely alligned in the figure

        else:  #speaker is Viking
          pop2_utterances[speaker.location].add_utterance(utterance)
          pop2_bookkeep[speaker.location].append(pop2_utterances[speaker.location].Total.V2_fraction())
          x_2[speaker.location].append(interaction_number) # generate values for x axis. This is necesarry to have both bookkeeping arrays nicely alligned in the figure

        if interaction_number % parms.PRINT_EVERY_N == 0:
          print('{:6}%'.format(round(100*interaction_number/parms.NR_OF_INTERACTIONS,1)), end='')
          for location in range(parms.NUM_LOCATIONS):
            if pop1_utterances[location].Total.Total > 0:
              print('   {:.4f}'.format(pop1_utterances[location].Total.V2_fraction()), end='')
            else:
              print('     --  ', end='')
            if pop2_utterances[location].Total.Total > 0:
              print(' {:.4f}'.format(pop2_utterances[location].Total.V2_fraction()), end='')
            else:
              print('   --  ', end='')
          print()


        # if parms.USE_DEATH == 1 and parms.DO_REMOVE_EXEMPLARS:  #do you want to use death. If you do not remove exemplars. This will not work anyway.
        if parms.DO_REMOVE_EXEMPLARS:  #do you want to use death. If you do not remove exemplars. This will not work anyway.
        #death. If speaker has x exemplars left, he dies
            if speaker.utterances.Total.Total == 1:
                location = speaker.location
                if speaker.POP_TYPE == 1:
                    population_1.pop(population_1.index(speaker))   # speaker dies
                    population_1.append(Celt(parms, location))      # new agent gets born
                elif speaker.POP_TYPE == 2:
                    population_2.pop(population_2.index(speaker))
                    population_2.append(Viking(parms, location))

        if parms.USE_DEATH == 2:  #do you want to use death. If you do not remove exemplars. This will not work anyway.
        #death. If speaker has x exemplars left, he dies
            for agent in (speaker, listener):
                if agent.count_speak + agent.count_hear >= parms.DIE_AFTER_N:
                    location = agent.location
                    if agent.POP_TYPE == 1:
                        population_1.pop(population_1.index(agent))   # agent dies
                        population_1.append(Celt(parms, location))    # new agent gets born
                    elif agent.POP_TYPE == 2:
                        population_2.pop(population_2.index(agent))
                        population_2.append(Viking(parms, location))

      plt.figure().set_size_inches(parms.NUM_LOCATIONS*5,4)                 
      for location in range(parms.NUM_LOCATIONS):
          plt.subplot(1, parms.NUM_LOCATIONS, location + 1)
          plt.ylim([0,1])
          plt.plot(x_1[location], pop1_bookkeep[location], 'r' )   # plot population 1 in red
          plt.plot(x_2[location], pop2_bookkeep[location], 'b' )   # plot population 2 in blue


  #generate filename and save output.
  timestr = time.strftime("%Y_%m_%d-%H_%M_%S") # To give any output file a unique name, the filename is based on the current time

  figname = "fig__" + timestr + ".png"
  plt.savefig(figname)
  print ("Plot saved as '{}'.".format(figname))

  parmout = "parms__" + timestr + ".txt"
  parms_stuff = pd.read_csv(parmfile, delimiter = "=", header=None, index_col=0)  #ugly, but works
  parms_stuff.to_csv(parmout, sep = '=')
  print ("Parameter settings saved as '{}'.".format(parmout))

  print("FINISHED")


if __name__ == '__main__':
  main()
