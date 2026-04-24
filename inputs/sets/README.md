# Sets

## Formatting guidelines

- Primary sets (those that define elements that are not subsets of other sets):
  - No header column
  - One element per line
  - No element-wise comments; each line should contain only the element
- Subsets (groups of elements from other sets, either 1-dimensional or multidimensional):
  - Include a header column specifying the relevant primary sets
  - The header column should start with a `*`
    - Even 1-dimensional subsets should have a header column.
    So if the set `food` has elements `[apple, banana, cauliflower]`, the subset `fruit(food)` (specified by `fruit.csv`) has the following lines:
      - `*food`
      - `apple`
      - `banana`
- Don't use * for element expansion in GAMS
- Don't use * for full-line comments; only use it for the first (header) row in subset definitions
