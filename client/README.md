# The EnerGNN Feature Store Client

To store and manage your training data, EnerGNN uses the [EnerGNN Feature Store](https://github.com/energnn/energnn-feature-store).

This guide illustrates how to use the `FeatureStoreClient` to manage your problem instances, datasets, and training checkpoints in a centralized and remote manner.

The `FeatureStoreClient` allows you to:
- Register and load generation configurations.
- Register and load instances (`Problem`).
- Create, register, and load datasets (`ProblemDataset`).
- Use a `ProblemLoader` to load data during training.
- Manage remote checkpoints with `RemoteCheckpointManager`.

---

## Installation

To use the `FeatureStoreClient`, install the `energnn-feature-store-client` package from PyPI.
```shell
pip install energnn-feature-store-client
```

---

## Client Initialization

The client requires the project name and the Feature Store service URL.

```python
from energnn_feature_store_client import FeatureStoreClient

fs_client = FeatureStoreClient(
    project_name="my_energnn_project",
    feature_store_url="http://localhost:8000"
)
```

---

## Instance Management (`Problem`)

A problem instance represents a specific configuration of a network or system to be studied.

Since `Problem` is an abstract class in `energnn`, you must implement your own problem class by defining graph retrieval methods (`get_context`, `get_gradient`, `get_metrics`, `get_metadata`), save logic (`save`), and graph structures (`context_structure`, `decision_structure`).

### Registering an instance
```python
from energnn.problem import Problem
from energnn.graph import JaxGraph, GraphStructure

from energnn_feature_store_client import ProblemMetadata

class MyCustomProblem(Problem):
    def __init__(self, name: str, config_id: str):
        # Initialize your instance with its specific parameters
        self.name = name
        self.config_id = config_id
        # ...

    def get_context(self, get_info: bool = False) -> tuple[JaxGraph, dict]:
        # Logic to extract the context graph (JaxGraph)
        # return context_graph, info_dict
        ...

    def get_gradient(self, *, decision: JaxGraph, get_info: bool = False) -> tuple[JaxGraph, dict]:
        # Calculate the gradient for a given decision
        # return gradient_graph, info_dict
        ...

    def get_metrics(self, *, decision: JaxGraph, get_info: bool = False) -> tuple[float, dict]:
        # Evaluate the decision (e.g., a scalar cost)
        # return metric_value, info_dict
        ...

    def save(self, *, path: str) -> None:
        # Serialize the instance for disk persistence
        ...

    @property
    def context_structure(self) -> GraphStructure:
        # Defines the expected structure for context graphs
        ...
        return GraphStructure(...)

    @property
    def decision_structure(self) -> GraphStructure:
        # Defines the expected structure for decision graphs
        ...
        return GraphStructure(...)



def get_metadata(problem: Problem) -> ProblemMetadata:
    # Returns metadata describing the instance
    return ProblemMetadata(
        name=problem.name,
        config_id=problem.config_id,
        # ...
    )
    
# Instantiate your custom problem
problem = MyCustomProblem(name="my_instance", config_id="config_1")

# Register in the Feature Store
success = fs_client.register_instance(problem)
```

### Downloading an instance
```python
from pathlib import Path

# Download to a local folder
fs_client.download_instance(
    name="my_instance",
    config_id="config_1",
    code_version=1,
    output_dir=Path("./data/instances")
)
```

---

## Dataset Management (`ProblemDataset`)

A `ProblemDataset` is a container (inheriting from `dict`) that groups metadata for a set of problem instances. It serves as an entry point for training by storing global information such as splits (`train`, `val`, `test`), maximum graph dimensions, and the list of `ProblemMetadata` for each instance.

### Create and register a dataset
To create a dataset, you must provide the list of instance metadata (`ProblemMetadata`) as well as global characteristics.

```python
from datetime import datetime
from energnn_feature_store_client import ProblemDataset, ProblemMetadata

# List of instance metadata (obtained via get_metadata() on your Problem objects)
instances_metadata = [
    ProblemMetadata(name="inst_1", config_id="cfg_1", code_version=1, ...),
    ProblemMetadata(name="inst_2", config_id="cfg_1", code_version=1, ...),
]

# Create the dataset
dataset = ProblemDataset(
    name="my_dataset",
    split="train",
    version=1,
    instances=instances_metadata,
    size=len(instances_metadata),
    ...
)

# Register in the Feature Store
fs_client.register_dataset(dataset)
```

### Loading a dataset
The client allows you to download the dataset file as well as all the instances it contains (problem files) to a local directory.

```python
from pathlib import Path

# Download and reconstruct the ProblemDataset object
dataset = fs_client.download_dataset(
    name="my_dataset",
    split="train",
    version=1,
    output_dir=Path("./data/datasets"),
    download_instances=True # Also downloads associated instances if missing locally
)

# Check for locally missing instances
missing = dataset.get_locally_missing_instances(path="./data/datasets")
```

---

## Data Loading (`ProblemLoader`)

Data loading for training relies on two abstract interfaces in `energnn`: `ProblemLoader` (the iterator) and `ProblemBatch` (the container for batched data).

### Implementing a `ProblemBatch` and a `ProblemLoader`

Since these classes are abstract, you must implement your own batching logic (for example, graph concatenation).

```python
from typing import Iterator
from energnn.problem import ProblemBatch, ProblemLoader, ProblemDataset
from energnn.graph import JaxGraph, GraphStructure

class MyCustomBatch(ProblemBatch):
    def __init__(self, instances):
        # Initialize with a list of Problem instances
        self.instances = instances
    
    def get_context(self, get_info: bool = False) -> tuple[JaxGraph, dict]:
        # Returns a JaxGraph grouping the batch contexts
        # return batched_context_graph, info_dict
        ...

    def get_gradient(self, *, decision: JaxGraph, get_info: bool = False) -> tuple[JaxGraph, dict]:
        # Calculates the gradient for a given batched decision
        # return gradient_graph, info_dict
        ...

    def get_score(self, *, decision: JaxGraph, get_info: bool = False) -> tuple[list[float], dict]:
        # Evaluates a scalar score for each instance in the batch
        # return list_of_scores, info_dict
        ...

    @property
    def context_structure(self) -> GraphStructure:
        # Structure of batched context graphs
        ...
        return GraphStructure(...)

    @property
    def decision_structure(self) -> GraphStructure:
        # Structure of batched decision graphs
        ...
        return GraphStructure(...)

class MyCustomLoader(ProblemLoader):
    def __init__(self, dataset: ProblemDataset, batch_size: int, shuffle: bool = False):
        self.dataset = dataset
        self.batch_size = batch_size
        self.shuffle = shuffle
        # ... iterator initialization
    
    def __iter__(self) -> Iterator[MyCustomBatch]:
        # Optional: shuffle data if shuffle=True
        return self

    def __next__(self) -> MyCustomBatch:
        # Returns the next MyCustomBatch
        # raises StopIteration at the end of the dataset
        ...

    def __len__(self) -> int:
        # Number of batches per epoch
        # eg: (len(self.dataset.instances) + self.batch_size - 1) // self.batch_size
        ...

    @property
    def context_structure(self) -> GraphStructure:
        ...
        return GraphStructure(...)

    @property
    def decision_structure(self) -> GraphStructure:
        ...
        return GraphStructure(...)
```

### Usage in the training loop

The `ProblemBatch` allows you to interact with the model without worrying about the complexity of batching.

```python
# Initialize your loader
loader = MyCustomLoader(dataset, batch_size=32, shuffle=True)

for batch in loader:
    # 1. Retrieve input data (context)
    context, info = batch.get_context()
    # Do stuff.
    ...
```

---

## Training and Remote Checkpoints

The `Trainer` class in EnerGNN orchestrates the training loop, evaluation, and checkpoint management. Coupled with the `RemoteCheckpointManager`, it allows automatically saving and synchronizing training state (model and optimizer) with the Feature Store.

### 1. Create an EnerGNN model and an optimizer

Training relies on the use of `flax.nnx` for the model and `optax` for gradient transformation (optimizer).

```python
from energnn.model.ready_to_use import TinyRecurrentEquivariantGNN
import optax

# Example model creation
model = TinyRecurrentEquivariantGNN(
    in_structure=loader.context_structure,
    out_structure=loader.decision_structure,
)

# Optimizer definition (e.g., Adam)
optimizer = optax.adam(learning_rate=1e-3)
```

### 2. Initialize the `Trainer` and start training

The `Trainer` handles passing batches, calculating gradients, and updating parameters.

```python
from energnn.trainer import Trainer

# Initialize the Trainer
trainer = Trainer(
    model=model,
    gradient_transformation=optimizer
)

# Start training
trainer.train(
    train_loader=train_loader,
    val_loader=val_loader,
    n_epochs=10
)
```
Model evaluation can be performed periodically, checkpoints can be saved using orbax and stored remotely with the Feature Store client.
### 3. Configure a `RemoteCheckpointManager`

Retrieve a manager via the Feature Store client so that backups are sent remotely.

```python
from energnn_feature_store_client import RemoteCheckpointManager

# Retrieve the manager via the client
ckpt_manager = fs_client.get_checkpoint_manager(
    run_id="run_2024_exp_01",
    directory="./checkpoints",
    ...
)

trainer.train(
    train_loader=train_loader,
    val_loader=val_loader,
    checkpoint_manager=ckpt_manager,
    n_epochs=10,
    optim_mode="minimize",  # "minimize" or "maximize"
    progress_bar=True
)
```

### 4. Restore a state

You can restore the complete state of the `Trainer` (including model weights, optimizer state, and current training step).

```python
# Restore the best checkpoint (local or remote via the ckpt_manager)
restored_ckpt_manager = fs_client.get_checkpoint_manager(
    run_id="run_2024_exp_01",
    directory="./restored_checkpoints",
    sync_from_remote=True, # to retrieve checkpoints stored from remote storage
    ...
)
trainer.load_checkpoint(restored_ckpt_manager, best=True)

# Training can be resumed or the model used for inference
print(f"Resuming training at step: {trainer.train_step}")
```
