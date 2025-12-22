import * as React from 'react';
import {
  PageSection,
  Title,
  Button,
  Alert,
  AlertVariant,
  Modal,
  ModalVariant,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Form,
  FormGroup,
  TextInput,
  TextArea,
  Spinner,
  EmptyState,
  EmptyStateBody,
  Toolbar,
  ToolbarContent,
  ToolbarItem,
  SearchInput,
  Content,
  Stack,
  StackItem,
  Drawer,
  DrawerContent,
  DrawerContentBody,
  DrawerPanelContent,
  DrawerHead,
  DrawerActions,
  DrawerCloseButton,
  DescriptionList,
  DescriptionListGroup,
  DescriptionListTerm,
  DescriptionListDescription,
  ActionGroup,
  Flex,
  FlexItem,
  Pagination,
} from '@patternfly/react-core';
import { Table, Tbody, Td, Th, Thead, Tr } from '@patternfly/react-table';
import SearchIcon from '@patternfly/react-icons/dist/esm/icons/search-icon';
import { EditIcon, TrashIcon } from '@patternfly/react-icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { itemService, ItemCreate, ItemUpdate } from '@app/services/itemService';
import { graphqlClient } from '@app/graphql/client';
import { ITEMS_QUERY } from '@app/graphql/queries';
import { ItemsQueryResult, ItemType } from '@app/graphql/types';

const ItemBrowser: React.FunctionComponent = () => {
  const queryClient = useQueryClient();

  // Search and filter state
  const [searchValue, setSearchValue] = React.useState('');
  const [debouncedSearchValue, setDebouncedSearchValue] = React.useState('');

  // Pagination state
  const [currentPage, setCurrentPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState(20);

  // Sorting state
  const [sortBy, setSortBy] = React.useState<string>('id');
  const [sortOrder, setSortOrder] = React.useState<'asc' | 'desc'>('asc');

  // Drawer state
  const [isDrawerExpanded, setIsDrawerExpanded] = React.useState(false);
  const [selectedItemId, setSelectedItemId] = React.useState<number | null>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = React.useState(false);
  const [editingItem, setEditingItem] = React.useState<ItemType | null>(null);
  const [formTitle, setFormTitle] = React.useState('');
  const [formDescription, setFormDescription] = React.useState('');

  // Success message state
  const [successMessage, setSuccessMessage] = React.useState<string | null>(null);

  // Debounce search input (300ms delay)
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchValue(searchValue);
      setCurrentPage(1); // Reset to first page when searching
    }, 300);

    return () => clearTimeout(timer);
  }, [searchValue]);

  // Clear success message after 3 seconds
  React.useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Fetch items with GraphQL via React Query
  const {
    data: itemsData,
    isLoading,
    error,
  } = useQuery({
    queryKey: [
      'items',
      {
        search: debouncedSearchValue || undefined,
        skip: (currentPage - 1) * pageSize,
        limit: pageSize,
        sortBy: sortBy,
        sortOrder: sortOrder,
      },
    ],
    queryFn: () =>
      graphqlClient.request<ItemsQueryResult>(ITEMS_QUERY, {
        search: debouncedSearchValue || undefined,
        skip: (currentPage - 1) * pageSize,
        limit: pageSize,
        sortBy: sortBy,
        sortOrder: sortOrder,
      }),
  });

  const items: ItemType[] = itemsData?.items ?? [];
  const totalCount = itemsData?.itemsCount ?? 0;

  const selectedItem = React.useMemo(
    () => items.find((item) => item.id === selectedItemId),
    [items, selectedItemId]
  );

  const selectedItemIndex = React.useMemo(
    () => items.findIndex((item) => item.id === selectedItemId),
    [items, selectedItemId]
  );

  // Mutations
  const createMutation = useMutation({
    mutationFn: (newItem: ItemCreate) => itemService.createItem(newItem),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      setSuccessMessage('Item created successfully');
      handleCloseModal();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, updates }: { id: number; updates: ItemUpdate }) =>
      itemService.updateItem(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      setSuccessMessage('Item updated successfully');
      handleCloseModal();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => itemService.deleteItem(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['items'] });
      setSuccessMessage('Item deleted successfully');
      setIsDrawerExpanded(false);
      setSelectedItemId(null);
    },
  });

  const handleRowClick = (itemId: number) => {
    setSelectedItemId(itemId);
    setIsDrawerExpanded(true);
  };

  const handleCloseDrawer = () => {
    setIsDrawerExpanded(false);
  };

  const handleSearchChange = (_event: React.FormEvent<HTMLInputElement>, value: string) => {
    setSearchValue(value);
  };

  const handleSearchClear = () => {
    setSearchValue('');
  };

  // Sort handler
  const handleSort = (_event: React.MouseEvent, column: string, direction: 'asc' | 'desc') => {
    setSortBy(column);
    setSortOrder(direction);
    setCurrentPage(1); // Reset to page 1 when sort changes
  };

  const handleFirstItem = () => {
    if (items.length > 0) {
      setSelectedItemId(items[0].id);
      setIsDrawerExpanded(true);
    }
  };

  const handlePreviousItem = () => {
    if (selectedItemIndex > 0) {
      setSelectedItemId(items[selectedItemIndex - 1].id);
    }
  };

  const handleNextItem = () => {
    if (selectedItemIndex < items.length - 1) {
      setSelectedItemId(items[selectedItemIndex + 1].id);
    }
  };

  const handleLastItem = () => {
    if (items.length > 0) {
      setSelectedItemId(items[items.length - 1].id);
      setIsDrawerExpanded(true);
    }
  };

  const handleOpenCreateModal = () => {
    setEditingItem(null);
    setFormTitle('');
    setFormDescription('');
    setIsModalOpen(true);
  };

  const handleOpenEditModal = (item: ItemType) => {
    setEditingItem(item);
    setFormTitle(item.title);
    setFormDescription(item.description || '');
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setEditingItem(null);
    setFormTitle('');
    setFormDescription('');
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (editingItem) {
      updateMutation.mutate({
        id: editingItem.id,
        updates: {
          title: formTitle,
          description: formDescription || undefined,
        },
      });
    } else {
      createMutation.mutate({
        title: formTitle,
        description: formDescription || undefined,
      });
    }
  };

  const handleDelete = async (item: ItemType) => {
    if (!confirm(`Are you sure you want to delete "${item.title}"?`)) {
      return;
    }
    deleteMutation.mutate(item.id);
  };

  // Column definitions for sorting
  const columns = [
    { key: 'id', label: 'ID', width: 10 as const },
    { key: 'title', label: 'Title', width: 20 as const },
    { key: 'description', label: 'Description', width: 35 as const },
    { key: 'owner', label: 'Owner', width: 20 as const, sortable: false },
    { key: 'actions', label: 'Actions', width: 15 as const, sortable: false },
  ];

  const mutationError = createMutation.error || updateMutation.error || deleteMutation.error;

  const panelContent = selectedItem && (
    <DrawerPanelContent widths={{ default: 'width_50' }}>
      <DrawerHead>
        <Stack hasGutter>
          <StackItem>
            <Title headingLevel="h2" size="xl">
              {selectedItem.title}
            </Title>
          </StackItem>
          <StackItem>
            <Content component="p">{selectedItem.description || 'No description provided'}</Content>
          </StackItem>
        </Stack>
        <DrawerActions>
          <DrawerCloseButton onClick={handleCloseDrawer} />
        </DrawerActions>
      </DrawerHead>
      <DrawerPanelContent>
        <Stack hasGutter>
          <StackItem>
            <DescriptionList isHorizontal>
              <DescriptionListGroup>
                <DescriptionListTerm>Item ID</DescriptionListTerm>
                <DescriptionListDescription>{selectedItem.id}</DescriptionListDescription>
              </DescriptionListGroup>
              <DescriptionListGroup>
                <DescriptionListTerm>Owner</DescriptionListTerm>
                <DescriptionListDescription>
                  {selectedItem.owner?.fullName || selectedItem.owner?.username || selectedItem.owner?.email || `User ${selectedItem.ownerId}`}
                </DescriptionListDescription>
              </DescriptionListGroup>
            </DescriptionList>
          </StackItem>
          <StackItem>
            <Stack hasGutter>
              <StackItem>
                <Title headingLevel="h3" size="md">
                  Actions
                </Title>
              </StackItem>
              <StackItem>
                <ActionGroup>
                  <Button variant="primary" onClick={() => handleOpenEditModal(selectedItem)}>Edit Item</Button>
                  <Button variant="danger" onClick={() => handleDelete(selectedItem)}>Delete</Button>
                </ActionGroup>
              </StackItem>
            </Stack>
          </StackItem>
          <StackItem>
            <Stack hasGutter>
              <StackItem>
                <Title headingLevel="h3" size="md">
                  Navigation
                </Title>
              </StackItem>
              <StackItem>
                <Flex spaceItems={{ default: 'spaceItemsSm' }}>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      onClick={handleFirstItem}
                      isDisabled={selectedItemIndex === 0}
                      size="sm"
                    >
                      First
                    </Button>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      onClick={handlePreviousItem}
                      isDisabled={selectedItemIndex === 0}
                      size="sm"
                    >
                      Previous
                    </Button>
                  </FlexItem>
                  <FlexItem>
                    <Content component="p">
                      Item {selectedItemIndex + 1} of {items.length}
                    </Content>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      onClick={handleNextItem}
                      isDisabled={selectedItemIndex === items.length - 1}
                      size="sm"
                    >
                      Next
                    </Button>
                  </FlexItem>
                  <FlexItem>
                    <Button
                      variant="secondary"
                      onClick={handleLastItem}
                      isDisabled={selectedItemIndex === items.length - 1}
                      size="sm"
                    >
                      Last
                    </Button>
                  </FlexItem>
                </Flex>
              </StackItem>
            </Stack>
          </StackItem>
        </Stack>
      </DrawerPanelContent>
    </DrawerPanelContent>
  );

  const drawerContent = (
    <Stack hasGutter>
      <StackItem>
        <Toolbar>
          <ToolbarContent>
            <ToolbarItem>
              <SearchInput
                placeholder="Search by title or description"
                value={searchValue}
                onChange={handleSearchChange}
                onClear={handleSearchClear}
                style={{ width: '400px' }}
              />
            </ToolbarItem>
            <ToolbarItem align={{ default: 'alignEnd' }}>
              <Button variant="primary" onClick={handleOpenCreateModal}>
                Add Item
              </Button>
            </ToolbarItem>
            <ToolbarItem variant="pagination">
              <Pagination
                itemCount={totalCount}
                perPage={pageSize}
                page={currentPage}
                onSetPage={(_event, newPage) => setCurrentPage(newPage)}
                onPerPageSelect={(_event, newSize) => {
                  setPageSize(newSize);
                  setCurrentPage(1);
                }}
                variant="top"
                widgetId="items-pagination-top"
                perPageOptions={[
                  { title: '10', value: 10 },
                  { title: '20', value: 20 },
                  { title: '50', value: 50 },
                  { title: '100', value: 100 },
                ]}
              />
            </ToolbarItem>
          </ToolbarContent>
        </Toolbar>
      </StackItem>
      <StackItem>
        {(error || mutationError) && (
          <Alert variant={AlertVariant.danger} title="Error" isInline>
            {error ? 'Failed to load items' : 'Operation failed'}
          </Alert>
        )}
        {successMessage && (
          <Alert variant={AlertVariant.success} title="Success" isInline>
            {successMessage}
          </Alert>
        )}
      </StackItem>
      <StackItem>
        {isLoading ? (
          <EmptyState>
            <Spinner size="xl" />
          </EmptyState>
        ) : items.length > 0 ? (
          <Table variant="compact">
            <Thead>
              <Tr>
                {columns.map((col, index) => {
                  if (col.sortable === false) {
                    return (
                      <Th key={col.key} width={col.width}>
                        {col.label}
                      </Th>
                    );
                  }
                  const isSorted = sortBy === col.key;
                  return (
                    <Th
                      key={col.key}
                      width={col.width}
                      sort={{
                        sortBy: {
                          index: isSorted ? index : undefined,
                          direction: sortOrder,
                        },
                        onSort: (_event, _index, direction) => handleSort(_event, col.key, direction),
                        columnIndex: index,
                      }}
                    >
                      {col.label}
                    </Th>
                  );
                })}
              </Tr>
            </Thead>
            <Tbody>
              {items.map((item) => (
                <Tr
                  key={item.id}
                  isClickable
                  isRowSelected={item.id === selectedItemId}
                  onRowClick={() => handleRowClick(item.id)}
                >
                  <Td dataLabel="ID">{item.id}</Td>
                  <Td dataLabel="Title">{item.title}</Td>
                  <Td dataLabel="Description">{item.description || <em>No description</em>}</Td>
                  <Td dataLabel="Owner">{item.owner?.fullName || item.owner?.username || item.owner?.email || `User ${item.ownerId}`}</Td>
                  <Td dataLabel="Actions" isActionCell>
                    <Flex spaceItems={{ default: 'spaceItemsNone' }}>
                      <FlexItem>
                        <Button
                          variant="plain"
                          aria-label="Edit item"
                          icon={<EditIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleOpenEditModal(item);
                          }}
                        />
                      </FlexItem>
                      <FlexItem>
                        <Button
                          variant="plain"
                          aria-label="Delete item"
                          icon={<TrashIcon />}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(item);
                          }}
                        />
                      </FlexItem>
                    </Flex>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        ) : totalCount === 0 && !searchValue ? (
          <EmptyState>
            <Title headingLevel="h4" size="lg">
              No items yet
            </Title>
            <EmptyStateBody>
              Create your first item to get started.
            </EmptyStateBody>
          </EmptyState>
        ) : (
          <EmptyState>
            <SearchIcon />
            <Title headingLevel="h4" size="lg">
              No items found
            </Title>
            <EmptyStateBody>Try adjusting your search criteria</EmptyStateBody>
          </EmptyState>
        )}
      </StackItem>
      {items.length > 0 && (
        <StackItem>
          <Pagination
            itemCount={totalCount}
            perPage={pageSize}
            page={currentPage}
            onSetPage={(_event, newPage) => setCurrentPage(newPage)}
            onPerPageSelect={(_event, newSize) => {
              setPageSize(newSize);
              setCurrentPage(1);
            }}
            variant="bottom"
            widgetId="items-pagination-bottom"
            perPageOptions={[
              { title: '10', value: 10 },
              { title: '20', value: 20 },
              { title: '50', value: 50 },
              { title: '100', value: 100 },
            ]}
          />
        </StackItem>
      )}
    </Stack>
  );

  return (
    <>
      <PageSection>
        <Stack hasGutter>
          <StackItem>
            <Title headingLevel="h1">Items</Title>
          </StackItem>
          <StackItem>
            <Content component="p">
              Search for items, view their details, and perform actions. Click on any row to view details in the side panel.
            </Content>
          </StackItem>
          <StackItem isFilled>
            <Drawer isExpanded={isDrawerExpanded} isInline>
              <DrawerContent panelContent={panelContent}>
                <DrawerContentBody>{drawerContent}</DrawerContentBody>
              </DrawerContent>
            </Drawer>
          </StackItem>
        </Stack>
      </PageSection>

      <Modal
        variant={ModalVariant.small}
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        aria-labelledby="item-modal-title"
        aria-describedby="item-modal-description"
      >
        <ModalHeader
          title={editingItem ? 'Edit Item' : 'Create Item'}
          description={editingItem ? 'Update the item details below.' : 'Enter the item details below.'}
          descriptorId="item-modal-description"
          labelId="item-modal-title"
        />
        <ModalBody>
          <Form id="item-form" onSubmit={handleSubmit}>
            <FormGroup label="Title" isRequired fieldId="item-title">
              <TextInput
                isRequired
                type="text"
                id="item-title"
                name="item-title"
                value={formTitle}
                onChange={(_event, value) => setFormTitle(value)}
              />
            </FormGroup>
            <FormGroup label="Description" fieldId="item-description">
              <TextArea
                id="item-description"
                name="item-description"
                value={formDescription}
                onChange={(_event, value) => setFormDescription(value)}
                rows={4}
              />
            </FormGroup>
          </Form>
        </ModalBody>
        <ModalFooter>
          <Button
            key="submit"
            variant="primary"
            form="item-form"
            onClick={handleSubmit}
            isLoading={createMutation.isPending || updateMutation.isPending}
            isDisabled={createMutation.isPending || updateMutation.isPending}
          >
            {editingItem ? 'Update' : 'Create'}
          </Button>
          <Button key="cancel" variant="link" onClick={handleCloseModal}>
            Cancel
          </Button>
        </ModalFooter>
      </Modal>
    </>
  );
};

export { ItemBrowser };
