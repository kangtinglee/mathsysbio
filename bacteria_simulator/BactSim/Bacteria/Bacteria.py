import networkx as nx
import copy
from BactSim.Evolution import Evolution

def make_basic_bacteria(id):
    def make_edge_cfg(weight, scale = 1, atp = 0, evo_sd = 0):
        return {
            'weight' : weight,
            'scale' : scale,
            'atp': atp,
            'make_evolution_cls' : lambda w : Evolution(w, evo_sd)
        }

    def make_all_edge_cfgs(transport, es, atp):
        return {
            'transport' : transport,
            'es_complex' : es,
            'atp' : atp
        }

    bac = Bacteria(id, survival_atp = 4, repro_atp = 4, initial_atp = 50, max_amount_per_step = 20, survive_reset_nodes = False, penalize_edges=False)

    foods = ('glucose', 'sucrose', 'lactose')

    cfgs = {
        'glucose' : make_all_edge_cfgs(
            make_edge_cfg(0.5, evo_sd = 0.2, atp = 0.2),
            make_edge_cfg(0.5, evo_sd = 0.2, atp = 0.2),
            make_edge_cfg(0.5, evo_sd = 0.2, atp = 0.2, scale = 5)
        ),
        'sucrose': make_all_edge_cfgs(
            make_edge_cfg(0.005, evo_sd = 0.3, atp = 0.2),
            make_edge_cfg(0.005, evo_sd = 0.3, atp = 0.2),
            make_edge_cfg(0.005, evo_sd = 0.3, atp = 0.2, scale = 5)
        ),
        'lactose' : make_all_edge_cfgs(
            make_edge_cfg(0.5, evo_sd = 0.2, atp = 0.2),
            make_edge_cfg(0.5, evo_sd = 0.2, atp = 0.2),
            make_edge_cfg(0.5, evo_sd = 0.2, atp = 0.2, scale = 5)
        )
    }

    # assumption : quantity of enzymes are constant
    for food in foods:
        # nodes
        transported = 'transported_' + food
        es_complex = 'enz_' + food + '_complex'

        bac.add_node(food)
        bac.add_node(transported)
        bac.add_node(es_complex)
        bac.add_edge(food, transported, **cfgs[food]['transport'])
        bac.add_edge(transported, es_complex, **cfgs[food]['es_complex'])
        bac.add_edge(es_complex, 'atp', **cfgs[food]['atp'])

    # add transported_sucrose -> transported_glucose edge
    bac.add_edge('transported_sucrose', 'transported_glucose', 0.0000000000001,
                 lambda w: Evolution(w, 0.2), atp = 0.2)
    return bac

class Bacteria(object):
    """
    A class representing a single bacterial cell.

    Attributes
    -----------
    Access the attributes of a bacteria using `bact.attribute_name` (eg. `bact.id`)

    FYI and don't really do anything:
    - id (any)
    - generation (int) : number of ancestors. Only newly created cells (not daughter cells
    created using clone() or divide()) have a value of 0.
    - age (int) : number of timesteps this bacteria has been alive for. Only newly created
    cells (not daughter cells) have a value of 0. Daughter cells inherit the age of the parent
    cell.
    - last_food (None or dict) : dict of the food fed to this bacteria in the last timestep,
    or None if this bacteria has not been given any food before.

    Actually important:
    - survival_atp (number) : minimum ATP needed for survival
    - repro_atp (number) : minimum ATP needed to reproduce
    - graph (NetworkX.DiGraph) : represents the bacteria's internal genetic/metabolic network.
    See the next 3 sections for a more detailed description.
    - max_amount_per_step (number) : maximum amount of the source node which can be processed
    by each edge in 1 timestep. see the next_timestep() function.
    - penalize_edges (bool) : whether to penalize existence of redundant edges (see
    next_timestep function)
    - survive_num_timesteps (int >= 1) : number of timesteps to run at once in the survive
    function
    - survive_reset_nodes (bool) : whether to reset quantities of all nodes, except ATP, at the
    end of 1 'feeding' (see survive function)
    - survive_reset_food: (bool) whether to reset food after first timestep (see survive function)

    graph
    ------
    The graph contains nodes and edges which represnt the bacteria's internal genetic/metabolic
    network. Some quick notes:

    - *What is a node?* Each node can represent a either a gene/protein, or metabolic
    substrate/product/intermediate (in our current version of the bacteria they all represent
    metabolic substrates/products/intermediates).
    - *What is an edge?* Each edge represents a pathway, which is carried out in each timestep
    (see next_timestep() function).
    - *Identification* Each node has a unique name. Edges are identified by the names of their
    source node and destination node.
    - *Acessing nodes and edges* The attributes of each node/edge in the graph can be retrieved
    using the get_node() and get_edge() functions. See the next 2 sections for the attributes
    in each node and edge.

    Node Attributes
    ----------------
    These are the attributes which all nodes (in the graph) have. They also correspond to
    the keys in the dict returned by get_node().

    - amount (number) : current amount of this node
    - description (str) : description of this node

    Edge Attributes
    ---------------
    These are the attributes which all edges (in the graph) have. They also correspond to
    the keys in the dict returned by get_edge().

    - weight (number in (0,1]) : current weight of edge
    - atp_needed (number) : amount of ATP used per unit of source node consumed
    - scale (number)

    see the next_timestep() function to understand how weight, atp_needed and scale are used.

    - evolution (BactSim.Evolution.Evolution)
    - description (str) : description of this edge

    How to read the code
    ---------------------
    Similar/related types of functions in this class are grouped together, headed by comments
    like this `## Example ##`. The sections are summarized here:

    1. Adding nodes and edges
    2. Simulation functions : survival and reproduction
    3. Getting node amounts and edge weights
    4. Getting nodes and edges
    5. Displaying functions (AKA functions that return strings describing the bacteria)
    """

    def __init__(self, id,
                 survival_atp, repro_atp, initial_atp,
                 max_amount_per_step = 30,
                 penalize_edges = True,
                 survive_num_timesteps = 3, survive_reset_nodes = False,
                 survive_reset_food = True):
        """
        Creates a single Bacteria with the given ATP threshold for survival + reproduction
        and initial amount of ATP. Only the ATP node is created

        :param id: ID of this bacteria.
        :param survival_atp: minimum ATP needed for survival
        :param repro_atp: minimum ATP needed to reproduce
        :param initial_atp: intial amount of ATP in the cell. Should be greater than 0.

        Optional parameters:
        :param max_amount_per_step: (default:30) maximum amount of source node which can be
        processed by each edge in 1 timestep (see next_timestep function)

        :param penalize_edges: (default: True) whether to penalize existence of redundant edges
        (see next_timestep function)

        :param survive_num_timesteps: (default: 3. must be int >= 1) number of timesteps to
        run at once in the survive function
        :param survive_reset_nodes: (default: False) whether to reset quantities of all nodes,
        except ATP, at the end of 1 'feeding' (see survive function)
        :param survive_reset_food: (default: True) whether to reset food after first timestep
        (see survive function)
        """

        # Parameters -> attributes
        self.id = id
        self.survival_atp = survival_atp
        self.repro_atp = repro_atp
        self.initial_atp = initial_atp

        self.max_amount_per_step = max_amount_per_step
        self.penalize_edges = penalize_edges
        self.survive_num_timesteps = survive_num_timesteps
        self.survive_reset_nodes = survive_reset_nodes
        self.survive_reset_food = survive_reset_food

        # Other setup
        self.timestep = 0
        self.generation = 0
        self.last_food = None

        self.graph = nx.DiGraph()
        self.graph.add_node('atp', amount=initial_atp)


    ## Adding nodes and edges ##

    def add_node(self, name, initial_amount = 0, description = ''):
        self.graph.add_node(name, amount = initial_amount, description = '')

    def add_edge(self, src, dest, weight, make_evolution_cls = lambda w: Evolution(w, 0), atp = 0, scale = 1, description = ''):
        if src not in self.graph or dest not in self.graph:
            raise ValueError('src or dest node has not been created')
        self.graph.add_edge(src, dest, weight=weight, atp_needed = atp, evolution = make_evolution_cls(weight), scale = scale, description = description)


    ## Simulation functions: survival and reproduction ##

    def is_alive(self):
        return self.get_node('atp')['amount'] >= self.survival_atp

    def can_reproduce(self):
        return self.get_node('atp')['amount'] >= self.repro_atp

    def set_food(self, food, record):
        """
        Set the food nodes in this bacteria to the given quantities. Used in the survive
        function.

        :param food: dict of food name to amount
        :param record: bool for whether to set this cell's `last_food` to the food given
        """

        for (food_src, amount) in food.items():
            self.graph.nodes[food_src]['amount'] = amount
        if record:
            self.last_food = food.copy()

    def reset_nodes(self):
        """
        Set the amounts of all nodes, except for ATP, to 0. Used in the survive function.
        """

        for node in self.graph.nodes:
            if node == 'atp':
                continue
            self.graph.nodes[node]['amount'] = 0

    def next_timestep(self):
        """
        Increment timestep by 1 and update the graph. The edges in the graph are evaluated
        independently, ie. the amounts are only changed at the end of the timestep.

        Attributes which can be adjusted in the constructor:
        - penalize_edges (bool) : whether to penalize existence of edges not being used.
        - max_amount_per_step (number) : maximum amount of source node (substrate) that can
        be processed by each edge in 1 timestep
        """

        self.timestep += 1

        # sum of weights of outgoing edges for each node
        out_weights = {}
        for (src, dest, weight) in self.graph.edges.data('weight'):
            if src in out_weights:
                out_weights[src] += weight
            else:
                out_weights[src] = weight

        # update the graph
        increase_by = {}
        for (src, dest, data) in self.graph.edges.data():
            if dest not in increase_by:
                increase_by[dest] = 0

            # Not sure if this is a realistic way to distribute the src nodes between multiple products
            # but at least we don't have to reset all the amounts every generation
            src_available = self.get_amount(src) * data['weight'] / out_weights[src]
            src_used = data['weight'] * min(src_available, self.max_amount_per_step)
            dest_produced = src_used * data['scale']

            self.graph.nodes[src]['amount'] -= src_used # deduct src (substrate) used
            increase_by[dest] += dest_produced # increase dest (product) synthesized (at the end of timestep)
            if self.penalize_edges:
                self.graph.nodes['atp']['amount'] -= data['atp_needed'] * max(dest_produced, data['weight'])
            else:
                self.graph.nodes['atp']['amount'] -= data['atp_needed'] * dest_produced

        # increase the amounts for each node
        for (node, amount) in increase_by.items():
            if amount > 0:
                # it's not possible for a TF to actually decrease the amount of protein
                # only decrease its rate of production (?)
                self.graph.nodes[node]['amount'] += amount

    def survive(self, food):
        """
        Determines whether this bacterium will survive in this generation with the given
        quantities of food, and updates the state of the graph.

        Attributes which can be adjusted in the constructor:
        - survive_num_timesteps (int) : number of timesteps to run in total
        - survive_reset_food (bool) : whether to reset food after the first timestep
        - survive_reset_nodes (bool) : whether to reset the values of all nodes after the
        last timestep

        Alternatively, this function can be overwritten to customize the behavior further.
        The example at the bottom of this file. Note that this can make the survive_
        attributes meaningless.

        :param food: dict of food to amount
        :returns: a bool for whether this bacterium survives or not
        """

        self.set_food(food, record = True)

        self.next_timestep()
        # reset food amount
        if self.survive_reset_food:
            zero_food = dict.fromkeys(food, 0)
            self.set_food(zero_food, record = False)

        # run remaining timesteps
        for i in range(self.survive_num_timesteps -1):
            self.next_timestep()

        if self.survive_reset_nodes:
            self.reset_nodes()

        return self.is_alive()

    def clone(self, id):
        """
        Clones cell. The generation of the cloned cell increases by 1 from the parent cell.
        The cloned cell also inherits the age of the parent cell. The amount of each node in
        both this cell and its clone halve.

        :param id: ID of cloned cell
        :returns: the cloned cell
        """

        cloned_cell = copy.deepcopy(self)
        cloned_cell.id = id
        cloned_cell.generation += 1

        # half amount of all nodes in this and parent
        for cell in (self, cloned_cell):
            for node_name in cell.graph.nodes:
                cell.graph.nodes[node_name]['amount'] /= 2

        return cloned_cell

    def evolve(self):
        """Evolves (ie. possibly mutates) weights of all edges in this bacterium's graph"""

        for (src, dest, evolution) in self.graph.edges.data('evolution'):
            self.graph.edges[src, dest]['weight'] = evolution.getMutated()

    def divide(self, id):
        """Equivalent to this.clone(id) and using evolve() on the daughter cell."""

        daughter = self.clone(id)
        daughter.evolve()
        return daughter


    ## Getting node amounts and edge weights ##

    def get_amount(self, node):
        """
        Get the amount of a node.

        :param node: name of node
        :returns: its amount (int/float)
        :raises: ValueError if the node doesn't exist
        """

        if self.has_node(node):
            return self.graph.nodes[node]['amount']
        else:
            raise ValueError(f'No node called {node}')

    def get_weight(self, src, dest):
        """
        Get the weight of an edge.

        :param src: name of source node
        :param dest: name of destination node
        :returns: the weight
        :raises: ValueError if the edge doesn't exist
        """

        if self.has_edge(src, dest):
            return self.graph.edges[src, dest]['weight']
        else:
            raise ValueError(f'No edge from {src} to {dest}')


    ## Getting nodes and edges ##

    def has_node(self, name):
        return self.graph.has_node(name)

    def has_edge(self, src, dest):
        return self.graph.has_edge(src, dest)

    def get_node(self, name):
        """Returns the attributes of the named node, if it exists, otherwise throws a ValueError"""

        if self.graph.has_node(name):
            return self.graph.nodes[name]
        raise ValueError(f'No node called {name}')

    def get_all_nodes(self, names_only = False):
        """
        Returns all the nodes in this graph.

        :param names_only: (default: False) whether to return the names of the nodes only.
        :returns: a list of the node names or a dict of node names to their attributes (see names_only)
        """
        if names_only:
            return list(self.graph.nodes)
        else:
            return dict(self.graph.nodes.data())

    def get_edge(self, src, dest):
        """
        Returns the attributes of the edge from src node to dest node, if it exists,
        otherwise a ValueError is thrown.

        :param src: name of the source node of the edge
        :param dest: name of the destination node of the edge
        :returns: a dict of the edge attributes
        """

        if self.graph.has_edge(src, dest):
            return self.graph.get_edge_data(src, dest)
        raise ValueError(f'No edge from {src} to {dest}')

    def get_all_edges(self, names_only = False, copy_attr = True):
        """
        Returns all the edges in this graph and by default, together with their attributes
        Edge names are in the format of (src node name, dest node name)

        :param names_only: (default: False) whether return the edge names only.
        :param copy_attr: (default: True) whether return a deep copy of the attributes dict of each edge.
        If False, modifying the attribute dict will modify the actual edge attributes
        :returns: list of edge names or dict of edge names to attributes (see names_only)
        """

        if names_only:
            return list(self.graph.edges)
        else:
            d = {}
            for src, dest, data in self.graph.edges.data():
                d[(src,dest)] = copy.deepcopy(data) if copy_attr else data
            return d


    ## Displaying functions (AKA functions that return strings describing the bacteria) ##

    def edges_str(self):
        """Returns a string describing all the edges in this bacteria"""

        string = ''
        for name, data in sorted(self.get_all_edges(copy_attr = False).items()):
            string += str(name) + ' '
            string += str(data)
            string += '\n'
        return string

    def nodes_str(self):
        """Returns a string describing all the nodes in this Bacteria"""

        string = ''
        for name, data in sorted(self.get_all_nodes().items()):
            string += str(name) + ' '
            string += str(data)
            string += '\n'
        return string

    def config_str(self, compact = False):
        """Return a string describing various setting for this Bacteria"""
        string = ''
        for attr in ('survival_atp','repro_atp','initial_atp',
                     'max_amount_per_step','penalize_edges',
                     'survive_num_timesteps', 'survive_reset_nodes', 'survive_reset_food'):
            string += f'{attr}: {self.__dict__[attr]}'
            string += ', ' if compact else '\n'
        return string

    def __str__(self):
        string = f'Bacteria {self.id}, generation: {self.generation}, age: {self.timestep}\n' \
            + self.config_str() \
            + f'Last food: {self.last_food}\n' \
            + 'NODES\n' \
            + self.nodes_str() \
            + 'EDGES\n' \
            + self.edges_str()
        return string

    __repr__ = __str__

def testing():
    bac1 = make_basic_bacteria(1)
    print(bac1)
    print(bac1.get_amount('glucose'))
    print(bac1.get_weight('glucose', 'transported_glucose'))
    try:
        print(bac1.get_weight('glucose', 'lactose'))
    except ValueError as e:
        print(e)

    bac2 = bac1.divide(2)
    print(bac2)
    print(bac2.get_amount('glucose'))
    wt = bac2.get_weight('glucose', 'transported_glucose')
    print(wt)
    print(type(wt)) # TODO fix this

    print(bac1 is bac2)
    print(bac1.graph is bac2.graph)
    print(bac1.graph.nodes['glucose'] is bac2.graph.nodes['glucose'])
    print()

    food = {'glucose' : 5, 'sucrose' : 10, 'lactose' : 3}
    print('Food', food)
    print(bac1)
    import pprint
    for i in range(2):
        bac1.survive(food)
        pprint.pprint(bac1.get_all_nodes())

def overwrite_survive_example(id):
    """Returns a bacteria with the survive function overwritten (for illustration)"""
    bac = make_basic_bacteria(id)
    def custom_survive(self,food):
        self.set_food(food, record=True)
        self.next_timestep()
        self.set_food(dict.fromkeys(food,0),record=False)
        return self.is_alive()
    bac.survive = lambda food: custom_survive(bac,food)
    return bac

if __name__ == '__main__':
    bac = overwrite_survive_example(1)
    print(bac)
    print(bac.survive({'glucose': 10}))
    print(bac)
