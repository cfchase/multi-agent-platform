import * as React from 'react';
import {
  Alert,
  AlertActionCloseButton,
  Button,
  Dropdown,
  DropdownItem,
  DropdownList,
  MenuToggle,
  MenuToggleElement,
  PageSection,
} from '@patternfly/react-core';
import {
  Chatbot,
  ChatbotContent,
  ChatbotDisplayMode,
  ChatbotFooter,
  ChatbotHeader,
  ChatbotHeaderMain,
  ChatbotHeaderMenu,
  ChatbotHeaderTitle,
  ChatbotHeaderActions,
  ChatbotConversationHistoryNav,
  Message,
  MessageBar,
  MessageBox,
  MessageProps,
  Conversation,
} from '@patternfly/chatbot';

// MessageBox ref type - includes DOM properties and scroll method
interface MessageBoxRef extends HTMLDivElement {
  scrollToBottom?: (options?: { behavior?: 'auto' | 'smooth' }) => void;
}
import { ArrowDownIcon, RedoIcon, TrashIcon } from '@patternfly/react-icons';

import { ChatAPI, Chat as ChatType, ChatMessage, StreamingEvent, Flow } from './chatApi';
import userAvatar from '@app/images/user-avatar.svg';
import aiLogo from '@app/images/ai-logo-transparent.svg';

import '@patternfly/chatbot/dist/css/main.css';
import './Chat.css';

const ERROR_MESSAGE = 'Sorry, an error occurred. Click retry to try again.';
const DISPLAY_MODE = ChatbotDisplayMode.embedded;

function convertMessageToProps(msg: ChatMessage): MessageProps {
  const isUser = msg.role === 'user';
  return {
    id: msg.id.toString(),
    role: isUser ? 'user' : 'bot',
    content: msg.content,
    name: isUser ? 'You' : 'Assistant',
    avatar: isUser ? userAvatar : aiLogo,
    timestamp: new Date(msg.created_at).toLocaleString(),
    avatarProps: isUser ? { isBordered: true } : undefined,
  };
}

function Chat(): React.ReactElement {
  // Chat list state
  const [chats, setChats] = React.useState<ChatType[]>([]);
  const [selectedChatId, setSelectedChatId] = React.useState<number | null>(null);
  const [chatsLoading, setChatsLoading] = React.useState(true);
  const [isDrawerOpen, setIsDrawerOpen] = React.useState(true);

  // Flow selector state
  const [flows, setFlows] = React.useState<Flow[]>([]);
  const [selectedFlowName, setSelectedFlowName] = React.useState<string | null>(null);
  const [isFlowMenuOpen, setIsFlowMenuOpen] = React.useState(false);

  // Messages state
  const [messages, setMessages] = React.useState<MessageProps[]>([]);
  const [isSending, setIsSending] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState<string>();
  const [lastError, setLastError] = React.useState<{ message: string; chatId: number } | null>(null);

  // Operation error state (for displaying errors to user)
  const [operationError, setOperationError] = React.useState<string | null>(null);

  const historyRef = React.useRef<HTMLButtonElement>(null);
  const streamControllerRef = React.useRef<{ close: () => void } | null>(null);
  const messageBoxRef = React.useRef<MessageBoxRef | null>(null);
  const [userScrolledUp, setUserScrolledUp] = React.useState(false);
  const scrollDetectionTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Scroll utility functions
  const scrollToBottom = React.useCallback(() => {
    if (messageBoxRef.current?.scrollToBottom) {
      messageBoxRef.current.scrollToBottom({ behavior: 'smooth' });
    }
  }, []);

  const isScrolledNearBottom = React.useCallback((threshold = 100) => {
    if (!messageBoxRef.current) return true;
    const container = messageBoxRef.current;
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    return distanceFromBottom <= threshold;
  }, []);

  const handleScroll = React.useCallback(() => {
    if (scrollDetectionTimeoutRef.current) {
      clearTimeout(scrollDetectionTimeoutRef.current);
    }
    scrollDetectionTimeoutRef.current = setTimeout(() => {
      const nearBottom = isScrolledNearBottom();
      setUserScrolledUp(!nearBottom);
    }, 100);
  }, [isScrolledNearBottom]);

  // Load chats and flows on mount
  React.useEffect(() => {
    loadChats();
    loadFlows();
  }, []);

  const loadFlows = async () => {
    try {
      const response = await ChatAPI.getFlows();
      const flowData = response?.data || [];
      setFlows(flowData);
      if (flowData.length > 0 && !selectedFlowName) {
        // Use configured default flow, or first flow as fallback
        const defaultFlow = response?.default_flow;
        const flowExists = defaultFlow && flowData.some((f) => f.name === defaultFlow);
        setSelectedFlowName(flowExists ? defaultFlow : flowData[0].name);
      }
    } catch (err) {
      console.error('Failed to load flows:', err);
      setFlows([]);
    }
  };

  // Load messages when chat changes
  React.useEffect(() => {
    if (selectedChatId) {
      loadMessages(selectedChatId);
    } else {
      setMessages([]);
    }
  }, [selectedChatId]);

  const loadChats = async () => {
    setChatsLoading(true);
    setOperationError(null);
    try {
      const response = await ChatAPI.getChats();
      const chatData = response?.data || [];
      setChats(chatData);
      if (chatData.length > 0 && !selectedChatId) {
        setSelectedChatId(chatData[0].id);
      }
    } catch (err) {
      console.error('Failed to load chats:', err);
      setOperationError('Failed to load chats. Please try refreshing the page.');
      setChats([]);
    } finally {
      setChatsLoading(false);
    }
  };

  const loadMessages = async (chatId: number) => {
    setOperationError(null);
    try {
      const response = await ChatAPI.getMessages(chatId);
      const messageData = response?.data || [];
      setMessages(messageData.map(convertMessageToProps));
    } catch (err) {
      console.error('Failed to load messages:', err);
      setOperationError('Failed to load messages. Please try selecting the chat again.');
      setMessages([]);
    }
  };

  const handleNewChat = async () => {
    setOperationError(null);
    try {
      const newChat = await ChatAPI.createChat({ title: 'New Chat' });
      setChats((prev) => [newChat, ...prev]);
      setSelectedChatId(newChat.id);
      setMessages([]);
    } catch (err) {
      console.error('Failed to create chat:', err);
      setOperationError('Failed to create a new chat. Please try again.');
    }
  };

  const handleDeleteChat = async (chatId: number) => {
    setOperationError(null);
    try {
      await ChatAPI.deleteChat(chatId);
      setChats((prev) => prev.filter((c) => c.id !== chatId));
      if (selectedChatId === chatId) {
        const remaining = chats.filter((c) => c.id !== chatId);
        setSelectedChatId(remaining.length > 0 ? remaining[0].id : null);
        setMessages([]);
      }
    } catch (err) {
      console.error('Failed to delete chat:', err);
      setOperationError('Failed to delete chat. Please try again.');
    }
  };

  const handleSelectConversation = (
    _e: React.MouseEvent | undefined,
    itemId: string | number | undefined
  ) => {
    if (itemId) {
      setSelectedChatId(Number(itemId));
    }
  };

  const handleSend = async (message: string | number, retryMessageText?: string) => {
    const messageText = retryMessageText || (typeof message === 'string' ? message : message.toString());
    if (!messageText.trim() || isSending) return;

    // Create a new chat if none is selected
    let chatId = selectedChatId;
    if (!chatId) {
      try {
        const newChat = await ChatAPI.createChat({ title: 'New Chat' });
        setChats((prev) => [newChat, ...prev]);
        setSelectedChatId(newChat.id);
        chatId = newChat.id;
      } catch (err) {
        console.error('Failed to create chat:', err);
        setOperationError('Failed to create a new chat. Please try again.');
        return;
      }
    }

    setIsSending(true);
    setLastError(null);
    setUserScrolledUp(false);
    const timestamp = new Date().toLocaleString();
    const isRetry = !!retryMessageText;

    // Add user message immediately (unless retrying)
    const userMessage: MessageProps = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageText,
      name: 'You',
      avatar: userAvatar,
      timestamp,
      avatarProps: { isBordered: true },
    };

    // Add loading bot message
    const loadingBotMessage: MessageProps = {
      id: `bot-${Date.now()}`,
      role: 'bot',
      content: '',
      name: 'Assistant',
      avatar: aiLogo,
      timestamp,
      isLoading: true,
    };

    if (isRetry) {
      // Remove the error message and add new loading message
      setMessages((prev) => {
        const withoutError = prev.filter((msg) => !msg.content?.includes('error occurred'));
        return [...withoutError, loadingBotMessage];
      });
    } else {
      setMessages((prev) => [...prev, userMessage, loadingBotMessage]);
    }
    setAnnouncement(`Message from You: ${messageText}. Assistant is thinking...`);
    setTimeout(() => scrollToBottom(), 50);

    let accumulatedContent = '';

    const streamController = ChatAPI.createStreamingMessage(
      chatId,
      messageText,
      (event: StreamingEvent) => {
        if (event.type === 'content' && event.content) {
          accumulatedContent += event.content;
          // Update the bot message with accumulated content
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === loadingBotMessage.id
                ? { ...msg, content: accumulatedContent, isLoading: false }
                : msg
            )
          );
        } else if (event.type === 'done') {
          streamControllerRef.current = null;
          // Reload to get the saved message IDs
          loadMessages(chatId);
          setIsSending(false);
          setAnnouncement(`Assistant: ${accumulatedContent}`);

          // Update chat title if first message
          if (messages.length === 0) {
            const title = messageText.slice(0, 50) + (messageText.length > 50 ? '...' : '');
            ChatAPI.updateChat(chatId, { title }).then(() => loadChats());
          }
        } else if (event.type === 'error') {
          streamControllerRef.current = null;
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === loadingBotMessage.id
                ? { ...msg, content: ERROR_MESSAGE, isLoading: false }
                : msg
            )
          );
          setLastError({ message: messageText, chatId });
          setIsSending(false);
        }
      },
      (err) => {
        console.error('Streaming error:', err);
        streamControllerRef.current = null;
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === loadingBotMessage.id
              ? { ...msg, content: ERROR_MESSAGE, isLoading: false }
              : msg
          )
        );
        setLastError({ message: messageText, chatId });
        setIsSending(false);
      },
      () => {
        streamControllerRef.current = null;
        setIsSending(false);
      },
      selectedFlowName || undefined
    );

    streamControllerRef.current = streamController;
  };

  const handleStopStreaming = () => {
    if (streamControllerRef.current) {
      streamControllerRef.current.close();
      streamControllerRef.current = null;
    }
    setIsSending(false);
    // Update any loading message to show it was stopped
    setMessages((prev) =>
      prev.map((msg) =>
        msg.isLoading ? { ...msg, content: msg.content || '(Stopped)', isLoading: false } : msg
      )
    );
  };

  const handleRetry = () => {
    if (lastError && lastError.chatId === selectedChatId) {
      handleSend('', lastError.message);
    }
  };

  // Build conversations for the drawer
  const conversations: Conversation[] = chats.map((chat) => ({
    id: chat.id.toString(),
    text: chat.title,
    menuItems: (
      <DropdownItem
        key="delete"
        icon={<TrashIcon />}
        onClick={(e) => {
          e.stopPropagation();
          handleDeleteChat(chat.id);
        }}
      >
        Delete
      </DropdownItem>
    ),
  }));

  return (
    <PageSection isFilled hasBodyWrapper={false} padding={{ default: 'noPadding' }}>
      <Chatbot displayMode={DISPLAY_MODE}>
        <ChatbotConversationHistoryNav
          displayMode={DISPLAY_MODE}
          onDrawerToggle={() => setIsDrawerOpen(!isDrawerOpen)}
          isDrawerOpen={isDrawerOpen}
          setIsDrawerOpen={setIsDrawerOpen}
          activeItemId={selectedChatId?.toString()}
          onSelectActiveItem={handleSelectConversation}
          conversations={conversations}
          onNewChat={handleNewChat}
          isLoading={chatsLoading}
          drawerContent={
            <>
              <ChatbotHeader>
                <ChatbotHeaderMain>
                  <ChatbotHeaderMenu
                    ref={historyRef}
                    aria-expanded={isDrawerOpen}
                    onMenuToggle={() => setIsDrawerOpen(!isDrawerOpen)}
                  />
                  <ChatbotHeaderTitle>
                    {selectedChatId
                      ? chats.find((c) => c.id === selectedChatId)?.title || 'Chat'
                      : 'Research Assistant'}
                  </ChatbotHeaderTitle>
                </ChatbotHeaderMain>
                <ChatbotHeaderActions>
                  <Dropdown
                    isOpen={isFlowMenuOpen}
                    onOpenChange={(isOpen) => setIsFlowMenuOpen(isOpen)}
                    onSelect={() => setIsFlowMenuOpen(false)}
                    toggle={(toggleRef: React.Ref<MenuToggleElement>) => (
                      <MenuToggle
                        ref={toggleRef}
                        onClick={() => setIsFlowMenuOpen(!isFlowMenuOpen)}
                        isExpanded={isFlowMenuOpen}
                        isDisabled={flows.length === 0}
                      >
                        {selectedFlowName || 'Select Flow'}
                      </MenuToggle>
                    )}
                  >
                    <DropdownList>
                      {flows.map((flow) => (
                        <DropdownItem
                          key={flow.id}
                          onClick={() => setSelectedFlowName(flow.name)}
                          description={flow.description}
                        >
                          {flow.name}
                        </DropdownItem>
                      ))}
                    </DropdownList>
                  </Dropdown>
                </ChatbotHeaderActions>
              </ChatbotHeader>
              {operationError && (
                <Alert
                  variant="danger"
                  title={operationError}
                  actionClose={<AlertActionCloseButton onClose={() => setOperationError(null)} />}
                  isInline
                />
              )}
              <ChatbotContent>
                {userScrolledUp && (
                  <div className="pf-chatbot__jump-button">
                    <Button
                      variant="primary"
                      onClick={() => {
                        scrollToBottom();
                        setUserScrolledUp(false);
                      }}
                      icon={<ArrowDownIcon />}
                      aria-label="Scroll to bottom"
                      size="sm"
                    >
                      New messages
                    </Button>
                  </div>
                )}
                <MessageBox
                  ref={messageBoxRef}
                  announcement={announcement}
                  onScroll={handleScroll}
                >
                  {messages.map((message) => {
                    const hasError = message.content?.includes('error occurred');
                    const canRetry = hasError && lastError && lastError.chatId === selectedChatId;
                    const showCopyAction = message.role === 'bot' && !message.isLoading && !hasError;

                    return (
                      <Message
                        key={message.id}
                        {...message}
                        actions={
                          showCopyAction
                            ? {
                                copy: {
                                  onClick: () => navigator.clipboard.writeText(message.content || ''),
                                },
                              }
                            : undefined
                        }
                      >
                        {canRetry && (
                          <Button
                            variant="link"
                            icon={<RedoIcon />}
                            onClick={handleRetry}
                            isDisabled={isSending}
                          >
                            Retry
                          </Button>
                        )}
                      </Message>
                    );
                  })}
                </MessageBox>
              </ChatbotContent>
              <ChatbotFooter>
                <MessageBar
                  onSendMessage={handleSend}
                  isSendButtonDisabled={isSending}
                  hasStopButton={isSending}
                  handleStopButton={handleStopStreaming}
                />
              </ChatbotFooter>
            </>
          }
        />
      </Chatbot>
    </PageSection>
  );
};

export { Chat };
