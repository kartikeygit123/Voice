document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const recordButton = document.getElementById('record-button');
    const summarizeButton = document.getElementById('summarize-button');
    const statusDiv = document.getElementById('status');
    const audioPlayer = document.getElementById('audio-player');

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;

    // --- Helper Functions ---
    function addMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        messageDiv.textContent = text;
        chatBox.appendChild(messageDiv);
        // Scroll to the bottom
        chatBox.scrollTop = chatBox.scrollHeight;
        return messageDiv; // Return the created element
    }

    function showStatus(message, isLoading = false) {
        statusDiv.textContent = message;
        if (isLoading) {
            statusDiv.classList.add('loading');
        } else {
            statusDiv.classList.remove('loading');
        }
    }

    function playAudio(audioUrl) {
        if (audioUrl) {
            audioPlayer.src = audioUrl;
            audioPlayer.play().catch(e => console.error("Error playing audio:", e));
        }
    }

    // --- Event Handlers ---

    // Send text message
    async function sendTextMessage() {
        const message = userInput.value.trim();
        if (!message) return;

        addMessage(message, 'user');
        userInput.value = ''; // Clear input field
        showStatus('Sending...', true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            showStatus(''); // Clear status
            const botMessageDiv = addMessage(data.bot_response, 'bot');
            playAudio(data.audio_url); // Play the response audio

        } catch (error) {
            console.error('Error sending message:', error);
            showStatus('Error sending message.');
            addMessage('Sorry, something went wrong communicating with the server.', 'bot');
        }
    }

    // Handle Enter key in textarea
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevent default newline insertion
            sendTextMessage();
        }
    });

    sendButton.addEventListener('click', sendTextMessage);

    // Record audio message
    recordButton.addEventListener('click', async () => {
        if (isRecording) {
            // Stop recording
            mediaRecorder.stop();
            recordButton.textContent = 'Record';
            recordButton.classList.remove('recording');
            showStatus('Processing audio...');
            isRecording = false;
        } else {
            // Start recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = []; // Reset chunks

                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    showStatus('Processing audio...', true);
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' }); // Or 'audio/ogg' depending on browser support

                    // Create FormData to send the Blob
                    const formData = new FormData();
                    formData.append('audio_data', audioBlob, 'recording.webm'); // Add filename

                    try {
                        const response = await fetch('/recognize', {
                            method: 'POST',
                            body: formData, // Send as FormData
                        });

                        if (!response.ok) {
                             throw new Error(`HTTP error! status: ${response.status}`);
                        }

                        const data = await response.json();
                        showStatus(''); // Clear status

                        // Display recognized text (if successful)
                        if (data.recognized_text && data.recognized_text !== "[Audio not recognized]") {
                             addMessage(`You (via voice): ${data.recognized_text}`, 'user');
                        } else if (data.recognized_text === "[Audio not recognized]") {
                             addMessage(`[Audio not recognized by system]`, 'user');
                         }

                        // Display bot response and play audio
                        const botMessageDiv = addMessage(data.bot_response, 'bot');
                        playAudio(data.audio_url);


                    } catch (error) {
                        console.error('Error sending audio:', error);
                        showStatus('Error processing audio.');
                        addMessage('Sorry, there was an error processing your audio.', 'bot');
                    } finally {
                         // Clean up media stream tracks
                        stream.getTracks().forEach(track => track.stop());
                    }
                };

                mediaRecorder.start();
                recordButton.textContent = 'Stop';
                recordButton.classList.add('recording');
                showStatus('Recording...');
                isRecording = true;

            } catch (error) {
                console.error('Error accessing microphone:', error);
                showStatus('Could not access microphone. Please grant permission.');
                // Optionally display error to user in chat
                addMessage('Error: Could not access microphone. Please check permissions.', 'bot');
            }
        }
    });

    // Summarize conversation
    summarizeButton.addEventListener('click', async () => {
         showStatus('Generating summary...', true);
         try {
             const response = await fetch('/summarize', {
                 method: 'GET', // Or POST if you prefer
             });

             if (!response.ok) {
                 throw new Error(`HTTP error! status: ${response.status}`);
             }

             const data = await response.json();
             showStatus(''); // Clear status

             // Display summary in chat (as a bot message)
             const summaryMessage = `Summary:\n${data.summary}`;
             addMessage(summaryMessage, 'bot');
             playAudio(data.audio_url); // Play the summary audio

         } catch (error) {
             console.error('Error fetching summary:', error);
             showStatus('Error generating summary.');
             addMessage('Sorry, I could not generate the summary.', 'bot');
         }
    });


    // --- Initial Greeting Audio ---
    // Small delay to ensure page is ready and maybe play initial greeting automatically
     // You could fetch initial greeting audio URL from backend on page load if needed.
    // For simplicity, let's just log it. If you want the initial greeting spoken,
    // you'd need the backend '/' route to also generate TTS for the initial msg.
    console.log("Chatbot initialized.");
    // Optional: Automatically play initial greeting (requires backend modification)
    // const initialBotMessage = chatBox.querySelector('.message.bot');
    // if(initialBotMessage) {
    //    const initialText = initialBotMessage.textContent;
    //    // Call backend to get audio for initialText, then playAudio(url)
    // }

});