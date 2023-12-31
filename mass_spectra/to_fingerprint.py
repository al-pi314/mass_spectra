import argparse
from time import sleep

import pandas as pd
from chembl_webresource_client.unichem import unichem_client as unichem
from scyjava import config, jimport

config.endpoints.append('org.openscience.cdk:cdk-bundle:2.8')
InChIGeneratorFactory = jimport('org.openscience.cdk.inchi.InChIGeneratorFactory')
InChIToStructure = jimport('org.openscience.cdk.inchi.InChIToStructure')
DefaultChemObjectBuilder = jimport('org.openscience.cdk.DefaultChemObjectBuilder')

InchiGenerator = InChIGeneratorFactory.getInstance()
def inchi_to_atom_container(inchi):
    builderInstance = DefaultChemObjectBuilder.getInstance()
    intostruct = InchiGenerator.getInChIToStructure(inchi, builderInstance)
    return intostruct.getAtomContainer()

def inchikey_to_inchi(inchikey):
    ret = unichem.inchiFromKey(inchikey)
    if len(ret) == 0:
        return None
    return ret[0]['standardinchi']

AVAILABLE_FINGERPRINTS = [
    'AtomPairs2DFingerprinter',
    'CircularFingerprinter',
    'EStateFingerprinter',
    'ExtendedFingerprinter',
    'KlekotaRothFingerprinter',
    'MACCSFingerprinter',
    'PubchemFingerprinter',
    'SubstructureFingerprinter'
]

FINGERPRINT_ARGS = {
    'PubchemFingerprinter': [DefaultChemObjectBuilder.getInstance()]
}

CONVERSION_RETRY_COUNT = 3
CONVERSION_RETRY_DELAY = 1

def generate_fingerprint(fingerprint_array, inchi_array):
    fingerprints = {}
    for fp in fingerprint_array:
        print(f'Generating {fp} fingerprint')
        if fp not in AVAILABLE_FINGERPRINTS:
            raise ValueError(f'Fingerprint type {fp} not available. Options are: {AVAILABLE_FINGERPRINTS}')

        fingerprinter = jimport(f'org.openscience.cdk.fingerprint.{fp}')
        fingerprinter = fingerprinter(*FINGERPRINT_ARGS.get(fp, {}))

        fingerprints[f'{fp}'] = pd.DataFrame(columns=['inchi'] + [f'bit_{i}' for i in range(fingerprinter.getSize())])
        print(f'Converting {len(inchi_array)} InChI keys to {fingerprinter.getSize()} bit {fp} fingerprint')
        for inchi_idx, inchi in enumerate(inchi_array):
            for i in range(CONVERSION_RETRY_COUNT):
                try:
                    atom_container = inchi_to_atom_container(f'{inchi}')
                    if atom_container.getAtomCount() == 0:
                        converted = inchikey_to_inchi(inchi)
                        print(f'Converted InChI key {inchi} to {converted}')
                        atom_container = inchi_to_atom_container(converted)
                except Exception as e:
                    print(f'Error Number {i} at idx {inchi_idx} converting InChI key {inchi}: {e}')
                    sleep(CONVERSION_RETRY_DELAY)
                    continue
                break

            if atom_container.getAtomCount() == 0:
                print(f'Cound not convert InChI key {inchi}...skipping')
                continue
            fingerprint = fingerprinter.getBitFingerprint(atom_container).asBitSet()
            fingerprint = java_bitset_to_python_array(fingerprint)
            fingerprint = fingerprint[:fingerprinter.getSize()]

            fingerprints[f'{fp}'].loc[inchi_idx] = [inchi] + fingerprint     
    return fingerprints

def java_bitset_to_python_array(bitSet):
        bits = [0] * bitSet.size()
        for i in bitSet.stream().toArray():
            bits[i] = 1
        return bits
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Optional app description')

    parser.add_argument('InChI', type=str,
                        help='InChI key string to convert to fingerprint')
    parser.add_argument('Fingerprint', type=str, 
                        help=f'Fingerprint type to convert to. Options are: {AVAILABLE_FINGERPRINTS}')
    parser.add_argument('--inchi_array', action='store_true',
                        help='Accept array of InChI keys separated by commas')
    parser.add_argument('--fingerprint_array', action='store_true',
                        help='Accept array of fingerprint types separated by commas')

    args = parser.parse_args()

    if args.inchi_array:
        inchi_array = args.InChI.split(',')
    else:
        inchi_array = [args.InChI]

    if args.fingerprint_array:
        fingerprint_array = args.Fingerprint.split(',')
    else:
        fingerprint_array = [args.Fingerprint]

    try:
        fingerprints = generate_fingerprint(fingerprint_array, inchi_array)
    except ValueError as e:
        parser.error(e)