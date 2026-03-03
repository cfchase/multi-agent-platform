import * as React from 'react';
import {
  Alert,
  AlertActionCloseButton,
  AlertActionLink,
  Button,
  Dropdown,
  DropdownItem,
  DropdownList,
  ExpandableSection,
  MenuToggle,
  MenuToggleElement,
  PageSection,
  Tooltip,
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
  MessageBoxHandle,
  MessageProps,
  Conversation,
} from '@patternfly/chatbot';
import { ArrowDownIcon, TrashIcon } from '@patternfly/react-icons';

import { ChatAPI, Chat as ChatType, ChatMessage, Flow } from './chatApi';
import { useJobPolling } from './useJobPolling';
import userAvatar from '@app/images/user-avatar.svg';
import aiLogo from '@app/images/ai-logo-transparent.svg';

import '@patternfly/chatbot/dist/css/main.css';
import './Chat.css';

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

/** Format elapsed seconds as human-readable string. */
function formatElapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
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
  const [lastError, setLastError] = React.useState<{
    message: string;
    chatId: number;
    botMessageId: string;
    errorText: string;
  } | null>(null);
  const [errorMessages, setErrorMessages] = React.useState<Map<string, string>>(new Map());

  // Operation error state (for displaying errors to user)
  const [operationError, setOperationError] = React.useState<string | null>(null);

  // Job state
  const [activeJobId, setActiveJobId] = React.useState<number | null>(null);
  const [jobStartTime, setJobStartTime] = React.useState<Date | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = React.useState(0);
  const loadingBotMessageIdRef = React.useRef<string | null>(null);
  const originalMessageTextRef = React.useRef<string>('');

  // Use the polling hook
  const { data: jobData } = useJobPolling(activeJobId);

  const historyRef = React.useRef<HTMLButtonElement>(null);
  const messageBoxRef = React.useRef<MessageBoxHandle | null>(null);
  const [userScrolledUp, setUserScrolledUp] = React.useState(false);
  const scrollDetectionTimeoutRef = React.useRef<NodeJS.Timeout | null>(null);

  // Elapsed time timer
  React.useEffect(() => {
    if (!jobStartTime || !activeJobId) {
      setElapsedSeconds(0);
      return;
    }
    const interval = setInterval(() => {
      setElapsedSeconds(Math.round((Date.now() - jobStartTime.getTime()) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [jobStartTime, activeJobId]);

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
        // Check localStorage for cached flow preference
        const cachedFlow = localStorage.getItem('selectedFlowName');
        const cachedFlowExists = cachedFlow && flowData.some((f) => f.name === cachedFlow);
        if (cachedFlowExists) {
          setSelectedFlowName(cachedFlow);
        } else {
          // Fall back to server default or first flow
          const defaultFlow = response?.default_flow;
          const flowExists = defaultFlow && flowData.some((f) => f.name === defaultFlow);
          setSelectedFlowName(flowExists ? defaultFlow : flowData[0].name);
        }
      }
    } catch (err) {
      console.error('Failed to load flows:', err);
      setFlows([]);
    }
  };

  // Load messages and check for active jobs when chat changes
  React.useEffect(() => {
    setLastError(null);
    setErrorMessages(new Map());
    if (selectedChatId) {
      const chat = chats.find((c) => c.id === selectedChatId);
      if (chat?.flow_name) {
        setSelectedFlowName(chat.flow_name);
      }
      // Skip loading messages if we're currently sending -- handleSend manages
      // messages directly and loadMessages would overwrite the loading indicator.
      if (!isSending) {
        loadMessages(selectedChatId);
        // Page refresh recovery: check for active jobs
        checkForActiveJob(selectedChatId);
      }
    } else {
      setMessages([]);
      setActiveJobId(null);
      setJobStartTime(null);
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

  /**
   * Page refresh recovery: check if there's an active (non-terminal) job for this chat.
   * If found, resume polling and show the typing indicator.
   */
  const checkForActiveJob = async (chatId: number) => {
    try {
      const activeJob = await ChatAPI.getActiveJob(chatId);
      if (activeJob) {
        // Resume polling for the active job
        setActiveJobId(activeJob.id);
        setJobStartTime(activeJob.started_at ? new Date(activeJob.started_at) : new Date());
        setIsSending(true);

        // Find the placeholder assistant message and show it as loading
        const botMsgId = `recovered-bot-${activeJob.chat_message_id}`;
        loadingBotMessageIdRef.current = botMsgId;

        // Add a loading indicator for the recovered job
        setMessages((prev) => {
          // Check if the last message is the empty placeholder
          const lastMsg = prev[prev.length - 1];
          if (lastMsg && lastMsg.role === 'bot' && !lastMsg.content) {
            // Replace the empty placeholder with a loading indicator
            return prev.map((msg, i) =>
              i === prev.length - 1
                ? { ...msg, id: botMsgId, isLoading: true }
                : msg
            );
          }
          // Otherwise add a loading message
          return [
            ...prev,
            {
              id: botMsgId,
              role: 'bot' as const,
              content: '',
              name: 'Assistant',
              avatar: aiLogo,
              timestamp: new Date().toLocaleString(),
              isLoading: true,
            },
          ];
        });
      }
    } catch {
      // No active job -- expected for most chats
    }
  };

  // React to job status changes
  React.useEffect(() => {
    if (!jobData || !activeJobId) return;
    const botMessageId = loadingBotMessageIdRef.current;
    if (!botMessageId) return;

    if (jobData.status === 'completed' && jobData.result_content) {
      // Update the bot message with the result
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? { ...msg, content: jobData.result_content!, isLoading: false }
            : msg
        )
      );
      // Reload messages to get server-side IDs
      if (selectedChatId) {
        loadMessages(selectedChatId);
      }
      setIsSending(false);
      setActiveJobId(null);
      setJobStartTime(null);
      loadingBotMessageIdRef.current = null;
      setAnnouncement(`Assistant: ${jobData.result_content}`);

      // Update chat title on first real message (only user+loading = length 2)
      if (messages.length <= 2 && selectedChatId) {
        const originalText = originalMessageTextRef.current;
        if (originalText) {
          const title = originalText.slice(0, 50) + (originalText.length > 50 ? '...' : '');
          ChatAPI.updateChat(selectedChatId, { title }).then(() => loadChats());
          const sendFlowName = isFlowLocked ? selectedChat?.flow_name : selectedFlowName;
          if (sendFlowName) {
            setChats((prev) =>
              prev.map((c) =>
                c.id === selectedChatId ? { ...c, flow_name: sendFlowName } : c
              )
            );
          }
        }
      }
    } else if (jobData.status === 'failed' || jobData.status === 'timed_out') {
      const errorText = jobData.error_message || 'An unknown error occurred.';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? { ...msg, content: '', isLoading: false }
            : msg
        )
      );
      setErrorMessages((prev) => new Map(prev).set(botMessageId, errorText));
      setLastError({
        message: originalMessageTextRef.current,
        chatId: selectedChatId!,
        botMessageId,
        errorText,
      });
      setIsSending(false);
      setActiveJobId(null);
      setJobStartTime(null);
      loadingBotMessageIdRef.current = null;
    } else if (jobData.status === 'cancelled') {
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? { ...msg, content: 'Request cancelled', isLoading: false }
            : msg
        )
      );
      setIsSending(false);
      setActiveJobId(null);
      setJobStartTime(null);
      loadingBotMessageIdRef.current = null;
    }
  }, [jobData]);

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

    // Require a valid flow to be selected
    const sendFlowName = isFlowLocked ? selectedChat?.flow_name : selectedFlowName;
    if (!sendFlowName || !flows.some((f) => f.name === sendFlowName)) {
      setOperationError(
        isFlowLocked
          ? 'This chat is locked to a flow that is no longer available.'
          : 'Please select a flow before sending a message.'
      );
      return;
    }

    // Auto-create chat if none exists
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
    setActiveJobId(null);
    setJobStartTime(new Date());
    setUserScrolledUp(false);
    originalMessageTextRef.current = messageText;
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
    const botMessageId = `bot-${Date.now()}`;
    loadingBotMessageIdRef.current = botMessageId;
    const loadingBotMessage: MessageProps = {
      id: botMessageId,
      role: 'bot',
      content: '',
      name: 'Assistant',
      avatar: aiLogo,
      timestamp,
      isLoading: true,
    };

    if (isRetry) {
      // Remove the error message and add new loading message
      const errorBotId = lastError?.botMessageId;
      if (errorBotId) {
        setErrorMessages((prev) => {
          const next = new Map(prev);
          next.delete(errorBotId);
          return next;
        });
      }
      setMessages((prev) => {
        const withoutError = prev.filter((msg) => msg.id !== errorBotId);
        return [...withoutError, loadingBotMessage];
      });
    } else {
      setMessages((prev) => [...prev, userMessage, loadingBotMessage]);
    }
    setAnnouncement(`Message from You: ${messageText}. Assistant is thinking...`);
    setTimeout(() => scrollToBottom(), 50);

    try {
      const jobResponse = await ChatAPI.createJobMessage(
        chatId, messageText, sendFlowName || undefined
      );
      setActiveJobId(jobResponse.id);
      // If the job already failed immediately (e.g., flow resolution error)
      if (jobResponse.status === 'failed') {
        const errorText = jobResponse.error_message || 'Failed to submit request.';
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === botMessageId
              ? { ...msg, content: '', isLoading: false }
              : msg
          )
        );
        setErrorMessages((prev) => new Map(prev).set(botMessageId, errorText));
        setLastError({ message: messageText, chatId, botMessageId, errorText });
        setIsSending(false);
        setActiveJobId(null);
        setJobStartTime(null);
        loadingBotMessageIdRef.current = null;
      }
    } catch (err) {
      // Handle immediate submission failure
      console.error('Failed to create job:', err);
      const errorText = err instanceof Error ? err.message : 'Failed to submit request.';
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === botMessageId
            ? { ...msg, content: '', isLoading: false }
            : msg
        )
      );
      setErrorMessages((prev) => new Map(prev).set(botMessageId, errorText));
      setLastError({ message: messageText, chatId, botMessageId, errorText });
      setIsSending(false);
      setActiveJobId(null);
      setJobStartTime(null);
      loadingBotMessageIdRef.current = null;
    }
  };

  const handleCancelJob = async () => {
    if (activeJobId) {
      try {
        await ChatAPI.cancelJob(activeJobId);
        // The useEffect watching jobData will handle the cancelled state on next poll
      } catch (err) {
        console.error('Failed to cancel job:', err);
        // Force local cancellation state
        const botMessageId = loadingBotMessageIdRef.current;
        if (botMessageId) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === botMessageId
                ? { ...msg, content: 'Request cancelled', isLoading: false }
                : msg
            )
          );
        }
        setIsSending(false);
        setActiveJobId(null);
        setJobStartTime(null);
        loadingBotMessageIdRef.current = null;
      }
    }
  };

  const handleRetry = () => {
    if (lastError && lastError.chatId === selectedChatId) {
      handleSend('', lastError.message);
    }
  };

  // Derived state for flow availability
  // Use the chat's locked flow_name as the source of truth when locked,
  // to avoid race conditions where loadFlows overwrites selectedFlowName.
  const selectedChat = chats.find((c) => c.id === selectedChatId);
  const isFlowLocked = !!selectedChat?.flow_name;
  const effectiveFlowName = isFlowLocked ? selectedChat.flow_name : selectedFlowName;
  const isFlowAvailable = !!effectiveFlowName && flows.some((f) => f.name === effectiveFlowName);

  // Derive job status text for tooltip
  const jobStatusText = React.useMemo(() => {
    if (!activeJobId || !jobData) return '';
    const statusLabel = jobData.status === 'in_progress' ? 'Running' :
      jobData.status === 'pending' ? 'Pending' : jobData.status;
    return `${statusLabel} - ${formatElapsed(elapsedSeconds)}`;
  }, [activeJobId, jobData, elapsedSeconds]);

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
                        isDisabled={flows.length === 0 || isFlowLocked}
                      >
                        {effectiveFlowName || 'Select Flow'}
                      </MenuToggle>
                    )}
                  >
                    <DropdownList>
                      {flows.map((flow) => (
                        <DropdownItem
                          key={flow.id}
                          onClick={() => {
                            setSelectedFlowName(flow.name);
                            localStorage.setItem('selectedFlowName', flow.name);
                          }}
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
                    const errorText = errorMessages.get(message.id || '');
                    const hasError = !!errorText;
                    const hasPartialContent = hasError && !!message.content;
                    const canRetry = hasError && lastError && lastError.chatId === selectedChatId;
                    const showCopyAction = message.role === 'bot' && !message.isLoading && !hasError;
                    const isActiveJobMessage = message.isLoading && !!activeJobId;

                    const retryLink = canRetry ? (
                      <AlertActionLink onClick={handleRetry} isDisabled={isSending}>
                        Retry
                      </AlertActionLink>
                    ) : undefined;

                    // Build extra content for active job loading messages (cancel button)
                    // and for error messages with expandable details
                    let extraContent: MessageProps['extraContent'] = undefined;

                    if (isActiveJobMessage) {
                      // Cancel button inline in typing indicator message area
                      extraContent = {
                        afterMainContent: (
                          <div className="pf-chatbot__job-cancel-area">
                            <Button
                              variant="link"
                              isDanger
                              onClick={handleCancelJob}
                              size="sm"
                            >
                              Cancel
                            </Button>
                          </div>
                        ),
                      };
                    } else if (hasError) {
                      // Error display with expandable details and retry
                      extraContent = {
                        afterMainContent: (
                          <div className="pf-chatbot__error-details">
                            <Alert
                              variant="danger"
                              title="An error occurred"
                              isInline
                              isPlain
                              actionLinks={retryLink}
                            />
                            <ExpandableSection toggleText="Show details" isIndented>
                              <pre className="pf-chatbot__error-pre">{errorText}</pre>
                            </ExpandableSection>
                          </div>
                        ),
                      };
                    }

                    // Wrap active job messages in a tooltip showing status + elapsed time
                    const messageElement = (
                      <Message
                        key={message.id}
                        {...message}
                        // Override content for error messages without partial content
                        {...(hasError && !hasPartialContent && !extraContent ? {} : {})}
                        actions={
                          showCopyAction
                            ? {
                                copy: {
                                  onClick: () => navigator.clipboard.writeText(message.content || ''),
                                },
                              }
                            : undefined
                        }
                        extraContent={extraContent}
                      />
                    );

                    if (isActiveJobMessage && jobStatusText) {
                      return (
                        <Tooltip key={message.id} content={jobStatusText}>
                          <div className="pf-chatbot__job-tooltip-wrapper">
                            {messageElement}
                          </div>
                        </Tooltip>
                      );
                    }

                    return messageElement;
                  })}
                </MessageBox>
              </ChatbotContent>
              <ChatbotFooter>
                {isFlowLocked && !isFlowAvailable && (
                  <Alert
                    variant="warning"
                    title={`This chat is locked to "${effectiveFlowName}" which is no longer available.`}
                    isInline
                    isPlain
                  />
                )}
                <MessageBar
                  onSendMessage={handleSend}
                  isSendButtonDisabled={isSending || !isFlowAvailable}
                  hasStopButton={isSending}
                  handleStopButton={handleCancelJob}
                />
              </ChatbotFooter>
            </>
          }
        />
      </Chatbot>
    </PageSection>
  );
}

export { Chat };
