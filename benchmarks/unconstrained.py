from profiles import Profiles

if __name__ == '__main__':
    profiles = Profiles(1, 5, 'unconstrained')
    profiles(['cobyqa', 'cg'], ['COBYQA', 'CG'])
